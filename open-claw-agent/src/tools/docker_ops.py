def docker_available() -> bool:
    try:
        import docker  # noqa
        return True
    except Exception:
        return False

def docker_ps() -> str:
    import docker
    client = docker.from_env()
    containers = client.containers.list(all=True)
    if not containers:
        return "No containers."
    lines = []
    for c in containers:
        name = c.name
        status = c.status
        image = (c.image.tags[0] if c.image.tags else str(c.image.id)[:12])
        lines.append(f"{name} | {status} | {image}")
    return "\n".join(lines)

def docker_restart(name: str) -> str:
    import docker
    client = docker.from_env()
    c = client.containers.get(name)
    c.restart()
    return f"Restarted: {name}"
