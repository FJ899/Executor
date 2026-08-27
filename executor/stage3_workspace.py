from __future__ import annotations

import ctypes
import hashlib
import os
import platform
import resource
import stat
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from executor.repository_access import RepositoryPathError, canonical_repository_path
from executor.stage3_evidence import sha256_bytes, sha256_json


class Stage3WorkspaceError(ValueError):
    pass


@dataclass(frozen=True)
class WorkspaceIdentity:
    repository: str
    commit: str
    tree: str
    head_sha256: str
    index_sha256: str
    tracked_path_count: int


@dataclass(frozen=True)
class TargetSnapshot:
    path: str
    device: int
    inode: int
    mode: int
    uid: int
    gid: int
    nlink: int
    size: int
    content_sha256: str
    xattrs_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "device": self.device,
            "inode": self.inode,
            "mode": self.mode,
            "uid": self.uid,
            "gid": self.gid,
            "nlink": self.nlink,
            "size": self.size,
            "content_sha256": self.content_sha256,
            "xattrs_sha256": self.xattrs_sha256,
        }


_GIT_SHA = set("0123456789abcdef")


def _require_git_sha(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or len(value) != 40 or any(c not in _GIT_SHA for c in value):
        raise Stage3WorkspaceError(f"{label} is not a lowercase SHA-1 object identity")
    return value


def _read_loose_object(git_dir: Path, oid: str) -> tuple[str, bytes]:
    _require_git_sha(oid, label="Git object")
    path = git_dir / "objects" / oid[:2] / oid[2:]
    try:
        compressed = path.read_bytes()
    except OSError as exc:
        raise Stage3WorkspaceError("pinned workspace requires locally materialized content-addressed Git objects") from exc
    try:
        raw = zlib.decompress(compressed)
    except zlib.error as exc:
        raise Stage3WorkspaceError("Git object is not a valid loose zlib object") from exc
    if hashlib.sha1(raw).hexdigest() != oid:
        raise Stage3WorkspaceError("Git object content identity mismatch")
    nul = raw.find(b"\x00")
    if nul <= 0:
        raise Stage3WorkspaceError("Git object header is malformed")
    try:
        kind, length_text = raw[:nul].decode("ascii").split(" ", 1)
        length = int(length_text)
    except (UnicodeError, ValueError) as exc:
        raise Stage3WorkspaceError("Git object header is malformed") from exc
    body = raw[nul + 1:]
    if length != len(body):
        raise Stage3WorkspaceError("Git object declared length mismatch")
    return kind, body


def _commit_tree(git_dir: Path, commit: str) -> str:
    kind, body = _read_loose_object(git_dir, commit)
    if kind != "commit":
        raise Stage3WorkspaceError("frozen source commit does not name a commit object")
    first = body.split(b"\n", 1)[0]
    if not first.startswith(b"tree "):
        raise Stage3WorkspaceError("commit object has no leading tree identity")
    try:
        tree = first[5:].decode("ascii")
    except UnicodeError as exc:
        raise Stage3WorkspaceError("commit tree identity is malformed") from exc
    return _require_git_sha(tree, label="commit tree")


def _tree_entries(git_dir: Path, tree: str, prefix: str = "") -> dict[str, tuple[str, str]]:
    kind, body = _read_loose_object(git_dir, tree)
    if kind != "tree":
        raise Stage3WorkspaceError("frozen source tree does not name a tree object")
    result: dict[str, tuple[str, str]] = {}
    offset = 0
    while offset < len(body):
        space = body.find(b" ", offset)
        nul = body.find(b"\x00", space + 1)
        if space <= offset or nul < 0 or nul + 21 > len(body):
            raise Stage3WorkspaceError("Git tree object is malformed")
        try:
            mode = body[offset:space].decode("ascii")
            name = body[space + 1:nul].decode("utf-8")
        except UnicodeError as exc:
            raise Stage3WorkspaceError("Git tree contains non-UTF-8 path") from exc
        if not name or "/" in name or name in {".", ".."}:
            raise Stage3WorkspaceError("Git tree contains an invalid path component")
        oid = body[nul + 1:nul + 21].hex()
        path = f"{prefix}/{name}" if prefix else name
        if mode == "40000":
            nested = _tree_entries(git_dir, oid, path)
            if set(result).intersection(nested):
                raise Stage3WorkspaceError("Git tree contains duplicate paths")
            result.update(nested)
        elif mode in {"100644", "100755", "120000", "160000"}:
            if path in result:
                raise Stage3WorkspaceError("Git tree contains duplicate path")
            result[path] = (mode, oid)
        else:
            raise Stage3WorkspaceError(f"unsupported Git tree mode: {mode}")
        offset = nul + 21
    return result


def _parse_index(index_bytes: bytes) -> dict[str, tuple[str, str]]:
    if len(index_bytes) < 32 or index_bytes[:4] != b"DIRC":
        raise Stage3WorkspaceError("Git index is malformed")
    version, count = struct.unpack(">II", index_bytes[4:12])
    if version not in {2, 3}:
        raise Stage3WorkspaceError("Git index version must be 2 or 3 for exact verification")
    body, checksum = index_bytes[:-20], index_bytes[-20:]
    if hashlib.sha1(body).digest() != checksum:
        raise Stage3WorkspaceError("Git index checksum mismatch")
    offset = 12
    result: dict[str, tuple[str, str]] = {}
    for _ in range(count):
        start = offset
        if offset + 62 > len(body):
            raise Stage3WorkspaceError("Git index entry is truncated")
        fields = struct.unpack(">10I20sH", body[offset:offset + 62])
        mode, oid, flags = fields[6], fields[10].hex(), fields[11]
        offset += 62
        if ((flags >> 12) & 0x3) != 0:
            raise Stage3WorkspaceError("Git index contains unmerged entries")
        if flags & 0x4000:
            if version < 3 or offset + 2 > len(body):
                raise Stage3WorkspaceError("Git index extended entry is malformed")
            offset += 2
        nul = body.find(b"\x00", offset)
        if nul < 0:
            raise Stage3WorkspaceError("Git index path is unterminated")
        try:
            path = body[offset:nul].decode("utf-8")
        except UnicodeError as exc:
            raise Stage3WorkspaceError("Git index contains non-UTF-8 path") from exc
        if not path or path in result:
            raise Stage3WorkspaceError("Git index contains invalid or duplicate path")
        offset = start + ((nul + 1 - start + 7) & ~7)
        if offset > len(body):
            raise Stage3WorkspaceError("Git index entry padding is malformed")
        modes = {0o100644:"100644",0o100755:"100755",0o120000:"120000",0o160000:"160000"}
        if mode not in modes:
            raise Stage3WorkspaceError(f"unsupported Git index mode: {mode:o}")
        result[path] = (modes[mode], oid)
    return result


def _blob_oid(data: bytes) -> str:
    raw = b"blob " + str(len(data)).encode("ascii") + b"\x00" + data
    return hashlib.sha1(raw).hexdigest()


def _verify_clean_worktree(repository_root: Path, tree_entries: dict[str, tuple[str, str]]) -> None:
    gitlinks = {path for path, (mode, _) in tree_entries.items() if mode == "160000"}
    observed: set[str] = set()
    for current, dirnames, filenames in os.walk(repository_root, topdown=True, followlinks=False):
        current_path = Path(current); rel_current = current_path.relative_to(repository_root)
        if rel_current == Path(".") and ".git" in dirnames: dirnames.remove(".git")
        retained_dirs = []
        for name in dirnames:
            rel = (rel_current / name).as_posix(); rel = rel[2:] if rel.startswith("./") else rel
            if rel in gitlinks: observed.add(rel)
            else: retained_dirs.append(name)
        dirnames[:] = retained_dirs
        for name in filenames:
            rel = (rel_current / name).as_posix(); observed.add(rel[2:] if rel.startswith("./") else rel)
    if observed != set(tree_entries):
        raise Stage3WorkspaceError("repository worktree is not exactly clean at frozen tree")
    for path, (mode, oid) in tree_entries.items():
        full = repository_root / path; info = full.lstat()
        if mode in {"100644","100755"}:
            if not stat.S_ISREG(info.st_mode): raise Stage3WorkspaceError(f"tracked regular file type mismatch: {path}")
            actual_mode = "100755" if info.st_mode & 0o111 else "100644"
            if actual_mode != mode: raise Stage3WorkspaceError(f"tracked file executable mode mismatch: {path}")
            if _blob_oid(full.read_bytes()) != oid: raise Stage3WorkspaceError(f"tracked file content mismatch: {path}")
        elif mode == "120000":
            if not stat.S_ISLNK(info.st_mode): raise Stage3WorkspaceError(f"tracked symlink type mismatch: {path}")
            if _blob_oid(os.readlink(full).encode("utf-8","surrogateescape")) != oid: raise Stage3WorkspaceError(f"tracked symlink content mismatch: {path}")
        elif mode == "160000":
            raise Stage3WorkspaceError("pinned Stage-3 workspace does not admit gitlinks because submodule cleanliness cannot be established by the in-process file verifier")


def verify_pinned_clean_workspace(repository_root: str | Path, *, repository: str, expected_repository: str, commit: str, tree: str) -> tuple[WorkspaceIdentity, dict[str, tuple[str, str]]]:
    root = Path(repository_root)
    if repository != expected_repository: raise Stage3WorkspaceError("repository identity mismatch")
    commit = _require_git_sha(commit, label="source commit"); tree = _require_git_sha(tree, label="source tree")
    git_dir = root / ".git"
    if not root.is_dir() or not git_dir.is_dir() or git_dir.is_symlink(): raise Stage3WorkspaceError("repository plane is not a regular Git worktree")
    head_bytes = (git_dir / "HEAD").read_bytes()
    if head_bytes != (commit + "\n").encode("ascii"): raise Stage3WorkspaceError("repository HEAD is not detached at exact frozen commit")
    if _commit_tree(git_dir, commit) != tree: raise Stage3WorkspaceError("source commit/tree binding mismatch")
    tree_entries = _tree_entries(git_dir, tree); index_bytes = (git_dir / "index").read_bytes()
    if _parse_index(index_bytes) != tree_entries: raise Stage3WorkspaceError("Git index does not exactly match frozen source tree")
    _verify_clean_worktree(root, tree_entries)
    return WorkspaceIdentity(repository, commit, tree, sha256_bytes(head_bytes), sha256_bytes(index_bytes), len(tree_entries)), tree_entries


def _open_beneath(root_fd: int, path: str, *, writable: bool) -> int:
    try: canonical = canonical_repository_path(path)
    except (RepositoryPathError, TypeError) as exc: raise Stage3WorkspaceError("mutation path is invalid") from exc
    parts = canonical.split("/"); current = os.dup(root_fd)
    try:
        for component in parts[:-1]:
            next_fd = os.open(component, os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC, dir_fd=current)
            os.close(current); current = next_fd
        return os.open(parts[-1], (os.O_RDWR if writable else os.O_RDONLY)|os.O_NOFOLLOW|os.O_CLOEXEC, dir_fd=current)
    except OSError as exc: raise Stage3WorkspaceError("secure beneath/no-follow target resolution failed") from exc
    finally:
        try: os.close(current)
        except OSError: pass


def _hash_fd(fd: int) -> tuple[str,int]:
    digest=hashlib.sha256(); offset=0
    while True:
        chunk=os.pread(fd,1024*1024,offset)
        if not chunk: break
        digest.update(chunk); offset += len(chunk)
    return digest.hexdigest(), offset


def _xattrs_hash(fd: int) -> str:
    try: names=sorted(os.listxattr(fd))
    except (AttributeError,OSError): names=[]
    values=[]
    for name in names:
        try: value=os.getxattr(fd,name)
        except OSError as exc: raise Stage3WorkspaceError("cannot read target extended attributes") from exc
        values.append({"name":name,"sha256":sha256_bytes(value),"size":len(value)})
    return sha256_json(values)


def snapshot_target_fd(fd:int, *, path:str, expected_hash:str|None=None)->TargetSnapshot:
    info=os.fstat(fd)
    if not stat.S_ISREG(info.st_mode): raise Stage3WorkspaceError("target is not a filesystem regular file")
    if info.st_nlink != 1: raise Stage3WorkspaceError("target link count must be exactly one")
    content_hash, byte_count = _hash_fd(fd)
    if byte_count != info.st_size: raise Stage3WorkspaceError("target size changed during read")
    if expected_hash is not None and content_hash != expected_hash: raise Stage3WorkspaceError("target content hash mismatch")
    return TargetSnapshot(path,info.st_dev,info.st_ino,stat.S_IMODE(info.st_mode),info.st_uid,info.st_gid,info.st_nlink,info.st_size,content_hash,_xattrs_hash(fd))


def open_validated_target_readonly(repository_root:str|Path, *, path:str, expected_before_sha256:str|None, tree_entries:dict[str,tuple[str,str]]) -> tuple[int,TargetSnapshot]:
    canonical=canonical_repository_path(path); tree_entry=tree_entries.get(canonical)
    if tree_entry is None or tree_entry[0] not in {"100644","100755"}: raise Stage3WorkspaceError("target is not an existing regular Git blob")
    root_fd=os.open(Path(repository_root),os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC)
    try: fd=_open_beneath(root_fd,canonical,writable=False)
    finally: os.close(root_fd)
    try:
        snap=snapshot_target_fd(fd,path=canonical,expected_hash=expected_before_sha256)
        if snap.mode != (0o755 if tree_entry[0]=="100755" else 0o644): raise Stage3WorkspaceError("target filesystem mode differs from Git tree mode")
        return fd,snap
    except Exception: os.close(fd); raise


def reopen_target_for_effect(repository_root:str|Path, *, path:str, pre_effect:TargetSnapshot)->int:
    root_fd=os.open(Path(repository_root),os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC)
    try: fd=_open_beneath(root_fd,path,writable=True)
    finally: os.close(root_fd)
    try:
        current=snapshot_target_fd(fd,path=path,expected_hash=pre_effect.content_sha256)
        if (current.device,current.inode,current.mode,current.uid,current.gid,current.nlink,current.size,current.xattrs_sha256)!=(pre_effect.device,pre_effect.inode,pre_effect.mode,pre_effect.uid,pre_effect.gid,pre_effect.nlink,pre_effect.size,pre_effect.xattrs_sha256): raise Stage3WorkspaceError("target identity changed between validation and effect opening")
        return fd
    except Exception: os.close(fd); raise


_PR_SET_NO_NEW_PRIVS=38; _PR_SET_SECCOMP=22; _SECCOMP_MODE_FILTER=2; _SECCOMP_RET_KILL_PROCESS=0x80000000; _SECCOMP_RET_ALLOW=0x7FFF0000; _AUDIT_ARCH_X86_64=0xC000003E; _BPF_LD_W_ABS=0x20; _BPF_JMP_JEQ_K=0x15; _BPF_RET_K=0x06
class _SockFilter(ctypes.Structure): _fields_=[("code",ctypes.c_ushort),("jt",ctypes.c_ubyte),("jf",ctypes.c_ubyte),("k",ctypes.c_uint32)]
class _SockFprog(ctypes.Structure): _fields_=[("len",ctypes.c_ushort),("filter",ctypes.POINTER(_SockFilter))]
def _stmt(code:int,k:int)->_SockFilter: return _SockFilter(code=code,jt=0,jf=0,k=k)
def _jump(code:int,k:int,jt:int,jf:int)->_SockFilter: return _SockFilter(code=code,jt=jt,jf=jf,k=k)

def _install_descriptor_only_seccomp()->None:
    if platform.system()!="Linux" or platform.machine() not in {"x86_64","AMD64"}: raise Stage3WorkspaceError("descriptor-only mutation worker requires Linux x86_64")
    allowed=[1,3,5,9,10,11,12,13,14,15,18,24,25,28,39,60,72,74,77,96,158,186,202,228,231,273,302,318,334]
    program=[_stmt(_BPF_LD_W_ABS,4),_jump(_BPF_JMP_JEQ_K,_AUDIT_ARCH_X86_64,1,0),_stmt(_BPF_RET_K,_SECCOMP_RET_KILL_PROCESS),_stmt(_BPF_LD_W_ABS,0)]
    for index,num in enumerate(allowed): program.append(_jump(_BPF_JMP_JEQ_K,num,len(allowed)-index,0))
    program.extend([_stmt(_BPF_RET_K,_SECCOMP_RET_KILL_PROCESS),_stmt(_BPF_RET_K,_SECCOMP_RET_ALLOW)])
    filters=(_SockFilter*len(program))(*program); fprog=_SockFprog(len=len(program),filter=filters); libc=ctypes.CDLL(None,use_errno=True)
    if libc.prctl(_PR_SET_NO_NEW_PRIVS,1,0,0,0)!=0: raise Stage3WorkspaceError(f"cannot set no_new_privs: errno={ctypes.get_errno()}")
    if libc.prctl(_PR_SET_SECCOMP,_SECCOMP_MODE_FILTER,ctypes.byref(fprog))!=0: raise Stage3WorkspaceError(f"cannot install descriptor-only seccomp: errno={ctypes.get_errno()}")


def _descriptor_only_replace(target_fd:int,replacement:bytes)->int:
    if not hasattr(os,"pwrite"): raise Stage3WorkspaceError("descriptor-only pwrite is unavailable")
    read_fd,write_fd=os.pipe2(os.O_CLOEXEC); success_receipt=b"OK"; replacement_view=memoryview(replacement); pid=os.fork()
    if pid==0:
        try:
            os.close(read_fd); keep=sorted({target_fd,write_fd}); soft,_=resource.getrlimit(resource.RLIMIT_NOFILE); upper=1_048_576 if soft==resource.RLIM_INFINITY else min(int(soft),1_048_576); start=0
            for kept in keep:
                if start<kept: os.closerange(start,kept)
                start=kept+1
            if start<upper: os.closerange(start,upper)
            view=replacement_view; receipt=success_receipt
            try: _install_descriptor_only_seccomp()
            except BaseException: os._exit(120)
            offset=0
            while offset<len(replacement):
                try: written=os.pwrite(target_fd,view[offset:offset+1024*1024],offset)
                except InterruptedError: continue
                except OSError as exc: os._exit(130+min(int(exc.errno or 0),50))
                except BaseException: os._exit(121)
                if written<=0: os._exit(111)
                offset+=written
            try: os.ftruncate(target_fd,len(replacement))
            except BaseException: os._exit(122)
            try: os.fsync(target_fd)
            except BaseException: os._exit(123)
            try: os.write(write_fd,receipt)
            except BaseException: os._exit(124)
            os._exit(0)
        except BaseException:
            try: os.write(write_fd,b"WORKER_FAIL")
            except BaseException: pass
            os._exit(112)
    os.close(write_fd); status_payload=b""
    try:
        while True:
            chunk=os.read(read_fd,4096)
            if not chunk: break
            status_payload+=chunk
    finally: os.close(read_fd)
    _,status=os.waitpid(pid,0)
    if not os.WIFEXITED(status) or os.WEXITSTATUS(status)!=0:
        detail=f"signal={os.WTERMSIG(status)}" if os.WIFSIGNALED(status) else f"exit={os.WEXITSTATUS(status)}" if os.WIFEXITED(status) else f"status={status}"
        raise Stage3WorkspaceError("descriptor-only mutation worker did not complete cleanly: "+detail)
    if status_payload!=success_receipt: raise Stage3WorkspaceError("descriptor-only mutation worker returned invalid receipt")
    return len(replacement)


def apply_exact_descriptor_replacement(target_fd:int, *, replacement:bytes, expected_after_sha256:str, pre_effect:TargetSnapshot)->tuple[TargetSnapshot,int]:
    if sha256_bytes(replacement)!=expected_after_sha256: raise Stage3WorkspaceError("replacement buffer does not match expected after hash")
    count=_descriptor_only_replace(target_fd,replacement); observed=snapshot_target_fd(target_fd,path=pre_effect.path,expected_hash=expected_after_sha256)
    if (observed.device,observed.inode,observed.mode,observed.uid,observed.gid,observed.nlink,observed.xattrs_sha256)!=(pre_effect.device,pre_effect.inode,pre_effect.mode,pre_effect.uid,pre_effect.gid,1,pre_effect.xattrs_sha256): raise Stage3WorkspaceError("target metadata changed across descriptor-only replacement")
    return observed,count
