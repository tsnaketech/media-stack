"""Load optional deployment extensions outside the Git checkout (stdlib only)."""
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def directory(root=ROOT):
    root = Path(root).resolve()
    value = os.environ.get('STACK_EXTENSIONS_DIR')
    if value is None:
        env = root.parent / '.env'
        if env.exists():
            for line in env.read_text().splitlines():
                if line.startswith('STACK_EXTENSIONS_DIR='):
                    value = line.split('=', 1)[1].strip().strip('\"\'')
    if not value:
        return None
    path = Path(value)
    if not path.is_absolute():
        raise ValueError('STACK_EXTENSIONS_DIR must be absolute')
    if not path.exists():
        return None
    return path.resolve()


def settings(root=ROOT):
    path = directory(root)
    if path is None:
        return {}
    manifest = path / 'extensions.json'
    if not manifest.is_file():
        raise ValueError('Extension directory has no extensions.json; deployment aborted')
    return json.loads(manifest.read_text())


def stack_directory(root, stack):
    path = settings(root).get('stacks', {}).get(str(stack))
    if path:
        return directory(root) / path
    base = (Path(root) / stack).resolve()
    if not base.exists() and not Path(stack).is_absolute():
        candidate = Path(root).parent / stack
        if (candidate / 'docker-compose.yml').exists():
            return candidate.resolve()
    return base


def compose_command(root, stack, arguments=()):
    root = Path(root).resolve()
    name = Path(stack).name
    base = stack_directory(root, stack)
    config = settings(root)
    command = ['docker', 'compose', '--project-directory', str(base)]
    shared_env = root.parent / '.env'
    if shared_env.exists():
        command += ['--env-file', str(shared_env)]
    if not shared_env.exists() and not (base / '.env').exists():
        command += ['--env-file', '/dev/null']
    if (base / '.env').exists():
        command += ['--env-file', str(base / '.env')]
    for file in config.get('env_files', {}).get(name, []):
        command += ['--env-file', str(directory(root) / file)]
    command += ['-f', str(base / 'docker-compose.yml')]
    for file in config.get('compose_overrides', {}).get(name, []):
        command += ['-f', str(directory(root) / file)]
    return command + list(arguments)


def management_directory(root, stack):
    """Keep common exports with the checkout and external stacks with extensions."""
    root = Path(root).resolve()
    name = Path(stack).name
    config = settings(root)
    enabled = config.get('management_exports')
    if enabled is None:
        enabled = [path.parent.name for path in root.glob('*/docker-compose.yml')]
    if name not in enabled:
        return None
    base = directory(root) if name in config.get('stacks', {}) else root.parent
    return base / 'runtime/arcane' / name


def store_management_model(root, stack, model):
    """Persist an effective Compose model for external container management UIs."""
    base = management_directory(root, stack)
    if base is None:
        return None
    base.mkdir(parents=True, exist_ok=True, mode=0o700)
    target = base / 'docker-compose.yml'
    import tempfile
    fd, temporary = tempfile.mkstemp(dir=base, prefix='.compose-')
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(model, stream, indent=2)
            stream.write('\n')
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return target


def refresh_management_model(root, stack):
    if management_directory(root, stack) is None:
        return
    import subprocess
    result = subprocess.run(compose_command(root, stack, ['config', '--format', 'json']),
                            check=True, capture_output=True, text=True)
    store_management_model(root, stack, json.loads(result.stdout))


def prepare_runtime_mounts(root, stack):
    """Create new writable runtime binds with their container user's ownership."""
    import subprocess
    result = subprocess.run(compose_command(root, stack, ['config', '--format', 'json']),
                            check=True, capture_output=True, text=True)
    runtime = Path(root).resolve().parent / 'runtime'
    for service in json.loads(result.stdout).get('services', {}).values():
        user = str(service.get('user', '')).split(':')
        env = service.get('environment', {})
        uid = int(user[0]) if user[0].isdigit() else int(env.get('PUID', 1000))
        gid = int(user[1]) if len(user) > 1 and user[1].isdigit() else int(env.get('PGID', 1000))
        for volume in service.get('volumes', []):
            if volume.get('type') != 'bind' or volume.get('read_only'):
                continue
            path = Path(volume['source'])
            if path.is_relative_to(runtime) and not path.exists():
                path.mkdir(parents=True, mode=0o700)
                if os.geteuid() == 0:
                    os.chown(path, uid, gid)
