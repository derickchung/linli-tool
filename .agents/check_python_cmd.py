import sys
import json
import re
import os

LOG_FILE = os.path.join(os.path.dirname(__file__), "hook_debug.log")

def main():
    try:
        raw_input = sys.stdin.read()
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[HOOK TRIGGERED] input len: {len(raw_input)}\n")
            f.write(f"{raw_input}\n")

        data = json.loads(raw_input)
        tool_call = data.get("toolCall", {})
        if tool_call.get("name") == "run_command":
            cmd = tool_call.get("args", {}).get("CommandLine", "")
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(f"[CMD] {cmd}\n")
            # 匹配 python -c, python3 -c, py -c, python.exe -c
            if re.search(r'^\s*(?:python\d*|py)(?:\.exe)?\s+-c\b', cmd, re.IGNORECASE):
                with open(LOG_FILE, "a", encoding="utf-8") as f:
                    f.write("[DECISION] ALLOW\n")
                print(json.dumps({"decision": "allow"}))
                return
    except Exception as e:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[ERROR] {e}\n")

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write("[DECISION] ASK\n")
    print(json.dumps({"decision": "ask"}))

if __name__ == "__main__":
    main()
