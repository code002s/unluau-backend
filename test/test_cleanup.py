import unittest

from unluau.cleanup import CleanupOptions, clean_source

from .helpers import find_luau, parses_as_luau, run_luau

DECOMPILER_STYLE = '''
local result = game:GetService("Players")
local result2 = game:GetService("ReplicatedStorage")
local result3 = result.LocalPlayer
local Parent = result3:WaitForChild("PlayerGui")
local Parent2 = Instance.new("ScreenGui")
Parent2.Name = "StaffStatsUI"
Parent2.Parent = Parent
local remote = result2:WaitForChild("StaffServerStatsRemote")
remote.OnClientEvent:Connect(function(a)
    if typeof(a) == "table" then
        if a.authorized == true then
            local value = a.serverFPS
            local value2 = tonumber(a.playerCount) or 0
            print(value, value2)
        end
    end
end)
'''


def cleaned(source: str, **options) -> str:
    result = clean_source(source, CleanupOptions(**options))
    assert result.cleaned, result.note
    return result.source


class RenameTest(unittest.TestCase):
    def test_meaningful_names_replace_decompiler_names(self):
        output = cleaned(DECOMPILER_STYLE)
        for expected in ("local Players =", "local ReplicatedStorage =", "local localPlayer =",
                         "local playerGui =", "local screenGui =", "local remote =",
                         "function(data)", "local serverFps =", "local playerCount ="):
            self.assertIn(expected, output)
        for artifact in ("result", "Parent2", "value2"):
            self.assertNotIn(artifact, output)

    def test_real_names_are_never_touched(self):
        source = "local count = 1\n\nlocal function helper(player)\n    return player + count\nend\n"
        self.assertEqual(cleaned(source, cache_services=False), source)

    def test_rename_never_captures_an_existing_name(self):
        source = ("local players = {}\n"
                  "local v = game:GetService(\"Players\")\n"
                  "local list = v:GetPlayers()\n"
                  "print(players, list)\n")
        output = cleaned(source, cache_services=False)
        self.assertIn("local Players = game:GetService(\"Players\")", output)
        self.assertIn("print(players, list)", output)

    def test_global_with_the_same_name_blocks_the_rename(self):
        source = "local v = Instance.new(\"Folder\")\nprint(v, folder)\n"
        output = cleaned(source)
        self.assertIn("local folder2 = Instance.new", output)
        self.assertIn("print(folder2, folder)", output)

    def test_unused_loop_key_becomes_underscore(self):
        output = cleaned("for k, v in pairs(t) do\n    print(v)\nend\n")
        self.assertIn("for _, v in pairs(t) do", output)


class FlowTest(unittest.TestCase):
    def test_nested_ifs_become_guard_clauses(self):
        output = cleaned(DECOMPILER_STYLE)
        self.assertNotIn("            if", output)  # nothing nested three deep any more
        self.assertIn("if typeof(data) ~= \"table\" then\n        return\n    end", output)
        self.assertIn("if data.authorized ~= true then\n        return\n    end", output)

    def test_loop_body_uses_continue(self):
        source = "for _, p in ipairs(list) do\n    if p.alive then\n        p:update()\n        p:draw()\n    end\nend\n"
        self.assertIn("if not p.alive then\n        continue\n    end", cleaned(source))

    def test_no_else_after_return(self):
        source = "local function f(x)\n    if x then\n        return 1\n    else\n        return 2\n    end\nend\n"
        self.assertEqual(cleaned(source), "local function f(x)\n    if x then\n        return 1\n    end\n\n    return 2\nend\n")

    def test_else_if_becomes_elseif(self):
        source = "if a then\n    f()\nelse\n    if b then\n        g()\n    else\n        h()\n    end\nend\n"
        self.assertIn("elseif b then", cleaned(source))

    def test_one_line_body_is_not_inverted(self):
        source = "local function f(x)\n    if x then\n        print(x)\n    end\nend\n"
        self.assertEqual(cleaned(source), source)

    def test_statement_starting_with_paren_gets_a_semicolon(self):
        source = "local function f(a, b)\n    if a then\n        local x = 1\n        (b or print)(x)\n    end\nend\n"
        output = cleaned(source)
        self.assertIn(";(b or print)(x)", output)


class ServicesTest(unittest.TestCase):
    def test_services_are_cached_once_at_the_top(self):
        source = ("local function a()\n    return game:GetService(\"Players\"):GetPlayers()\nend\n"
                  "local function b()\n    local p = game:GetService(\"Players\")\n    return p.LocalPlayer\nend\n")
        output = cleaned(source)
        self.assertEqual(output.count("GetService"), 1)
        self.assertTrue(output.startswith("local Players = game:GetService(\"Players\")\n"))
        self.assertIn("Players:GetPlayers()", output)
        self.assertIn("return Players.LocalPlayer", output)


class SafetyNetTest(unittest.TestCase):
    def test_unsupported_syntax_returns_the_original(self):
        source = "local function f(x: number): number\n    return x\nend\n"
        result = clean_source(source)
        self.assertFalse(result.cleaned)
        self.assertEqual(result.source, source)
        self.assertIn("skipped", result.note)

    def test_garbage_returns_the_original(self):
        result = clean_source("local = = =")
        self.assertFalse(result.cleaned)
        self.assertEqual(result.source, "local = = =")

    def test_comments_survive(self):
        output = cleaned("-- keep me\nlocal x = 1\n")
        self.assertIn("-- keep me", output)

    def test_cleanup_is_idempotent(self):
        once = cleaned(DECOMPILER_STYLE)
        self.assertEqual(cleaned(once), once)

    def test_strict_header_is_opt_in(self):
        self.assertFalse(cleaned("local x = 1\n").startswith("--!"))
        self.assertTrue(cleaned("local x = 1\n", strict_header=True).startswith("--!strict\n"))


@unittest.skipUnless(find_luau("luau-compile"), "luau-compile not found (set LUAU_DIR)")
class RealLuauSyntaxTest(unittest.TestCase):
    def test_output_is_accepted_by_the_luau_compiler(self):
        ok, error = parses_as_luau(cleaned(DECOMPILER_STYLE))
        self.assertTrue(ok, error)


# Pure-logic scripts: running before and after cleanup must print the same thing.
BEHAVIOUR_SAMPLES = {
    "guards": '''
local function classify(player)
    if player then
        if player.character then
            local humanoid = player.character.humanoid
            if humanoid then
                if humanoid.health > 0 then
                    return "alive:" .. humanoid.health
                else
                    return "dead"
                end
            else
                return "no humanoid"
            end
        end
    end
end
print(classify(nil))
print(classify({}))
print(classify({character = {}}))
print(classify({character = {humanoid = {health = 0}}}))
print(classify({character = {humanoid = {health = 7}}}))
''',
    "loops": '''
local seen = {}
for i = 1, 6 do
    local value = i * 2
    if i % 2 == 0 and value > 2 then
        seen[#seen + 1] = value
        seen[#seen + 1] = -value
    end
end
print(table.concat(seen, ","))
local n = 0
while n < 5 do
    n += 1
    if n ~= 3 then
        print("n", n)
        print("sq", n * n)
    end
end
''',
    "chains": '''
local function grade(score)
    if score >= 90 then
        return "A"
    else
        if score >= 80 then
            return "B"
        else
            if score >= 70 then
                return "C"
            else
                local note = "F" .. score
                return note
            end
        end
    end
end
for _, s in ipairs({95, 85, 75, 10}) do print(s, grade(s)) end
''',
    "naming": '''
local result = {3, 1, 2}
local value = 0
for k, v in ipairs(result) do
    value = value + v * k
end
local function Parent2(a)
    if a then
        local value2 = a * 2
        print("double", value2)
    end
end
Parent2(value)
Parent2(nil)
''',
}


@unittest.skipUnless(find_luau("luau"), "luau not found (set LUAU_DIR)")
class RuntimeEquivalenceTest(unittest.TestCase):
    def test_behaviour_is_unchanged(self):
        for name, source in BEHAVIOUR_SAMPLES.items():
            with self.subTest(name):
                before = run_luau(source)
                after = run_luau(cleaned(source))
                self.assertEqual(before.returncode, 0, before.stderr)
                self.assertEqual(after.returncode, 0, after.stderr)
                self.assertEqual(before.stdout, after.stdout)
                self.assertTrue(before.stdout.strip())


if __name__ == "__main__":
    unittest.main()
