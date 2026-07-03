def greet(name: str) -> str:
    cleaned = name.strip()
    if not cleaned:
        cleaned = "there"
    return f"Hello, {cleaned}!"
