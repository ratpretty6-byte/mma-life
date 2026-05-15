/**
 * Validation plugin for MMA Life Simulator
 * Hooks into tool.execute.after to run tests when Python files are edited.
 * Place this file in .opencode/plugins/ and it auto-loads.
 */
const { execSync } = require("child_process");
const path = require("path");

const PROJECT = path.resolve(__dirname, "../..");
const PYTHON_FILES = /\.py$/;

function runTests() {
  try {
    const result = execSync(
      "python3 -m unittest discover tests -v 2>&1",
      { cwd: PROJECT, timeout: 60000, encoding: "utf8" }
    );
    return { ok: true, output: result };
  } catch (e) {
    return { ok: false, output: e.stdout || e.message };
  }
}

/** @type {import('@opencode-ai/plugin').Plugin} */
module.exports = async () => {
  return {
    "tool.execute.after": async (input, output) => {
      if (!output || !output.result) return;

      // Check if any Python files were modified
      let pythonChanged = false;
      const args = input.args || {};
      if (args.filePath && PYTHON_FILES.test(args.filePath)) {
        pythonChanged = true;
      }
      if (args.oldString || args.newString) {
        pythonChanged = true;
      }

      if (!pythonChanged) return;

      const testResult = runTests();
      if (testResult.ok) {
        console.log("✓ All tests passed");
      } else {
        console.warn("⚠ Tests failed after edit:");
        console.warn(testResult.output);
      }
    },
  };
};
