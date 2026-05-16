/**
 * Validation plugin for MMA Life Simulator
 * Hooks into tool.execute.after to run tests when Python files are edited.
 * Now uses pytest + coverage for better output.
 */
const { execSync } = require("child_process");
const path = require("path");

const PROJECT = path.resolve(__dirname, "../..");
const PYTHON_FILES = /\.py$/;

const settings = {
  silentFail: false,    // set true to only log on failures
  showCoverage: true,   // toggle coverage summary
};

function runTests() {
  const covFlag = settings.showCoverage ? "--cov=. --cov-report=term-missing:skip-covered" : "";
  try {
    const result = execSync(
      `python3 -m pytest ${covFlag} -q --tb=short 2>&1`,
      { cwd: PROJECT, timeout: 90000, encoding: "utf8" }
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
        console.log("✓ Tests passed");
      } else {
        console.warn("⚠ Tests failed:");
        console.warn(testResult.output);
      }
    },
  };
};
