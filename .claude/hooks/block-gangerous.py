
import json
import sys


def extract_command(payload):
    if not isinstance(payload, dict):
        return None

    command_value = payload.get("command")
    if isinstance(command_value, str):
        return command_value

    tool_input = payload.get("tool_input")
    if isinstance(tool_input, dict):
        return extract_command(tool_input)

    return None

# step 1: read the json from stdin
data = json.load(sys.stdin)
# step 2: extract the bash command the model wants to run
command = extract_command(data) or ""
# step 3: define what we want to protect
protected_files = ["spendly.db", "venv", "migrations"]
# step 4: check if the command contains any of the dangerous commands
dangerous_tokens = ["rm", "unlink", "truncate", "remove-item", "delete", "del", "remove", ">"]
normalized_command = command.lower().replace("\\", "/")

#step 5: if the command contains any of the dangerous commands, check if it also contains any of the protected files
for token in dangerous_tokens:
    if token in normalized_command:
        for protected_file in protected_files:
            if protected_file in normalized_command:
                print(
                    f"Blocked cannot execute '{command}' because '{protected_file}' is protected",
                    file=sys.stderr,
                )
                sys.exit(2)

# step 6: otherwise allow the command
sys.exit(0)