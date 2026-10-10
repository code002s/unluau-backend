import os
import subprocess
import difflib

# Path to the unluac-cli binary
DECOMPILER_PATH = "./unluac-cli"
FIXTURES_DIR = "./test/fixtures"

def run_decompile(input_file):
    """Runs the decompiler and returns the output string."""
    try:
        result = subprocess.run(
            [DECOMPILER_PATH, "-i", input_file],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"ERROR: {e.stderr}"

def validate_fixtures():
    print("🔍 Starting Regression Tests...")
    passed = 0
    failed = 0

    # Iterate through all .luauc files in fixtures
    for filename in os.listdir(FIXTURES_DIR):
        if filename.endswith(".luauc"):
            bytecode_path = os.path.join(FIXTURES_DIR, filename)
            expected_path = bytecode_path.replace(".luauc", ".lua")

            if not os.path.exists(expected_path):
                print(f"⚠️ Skipping {filename}: No expected .lua file found.")
                continue

            with open(expected_path, "r", encoding="utf-8") as f:
                expected_source = f.read()

            actual_source = run_decompile(bytecode_path)

            if actual_source.strip() == expected_source.strip():
                print(f"✅ {filename}: PASSED")
                passed += 1
            else:
                print(f"❌ {filename}: FAILED")
                # Generate a diff to see exactly what changed
                diff = difflib.unified_diff(
                    expected_source.splitlines(),
                    actual_source.splitlines(),
                    fromfile='expected',
                    tofile='actual'
                )
                print('\n'.join(diff))
                failed += 1

    print(f"\n--- Results ---\nPassed: {passed}\nFailed: {failed}")
    if failed > 0:
        exit(1)

if __name__ == "__main__":
    validate_fixtures()
