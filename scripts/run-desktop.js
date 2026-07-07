const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

const desktopDir = path.join(__dirname, '..', 'appdesktop');
let command = 'python';
let args = ['main.py'];

// Posibles rutas del ejecutable de python en el entorno virtual
const venvPythonWin = path.join(desktopDir, '.venv', 'Scripts', 'python.exe');
const venvPythonUnix = path.join(desktopDir, '.venv', 'bin', 'python');
const envPythonWin = path.join(desktopDir, 'env', 'Scripts', 'python.exe');
const envPythonUnix = path.join(desktopDir, 'env', 'bin', 'python');

if (fs.existsSync(venvPythonWin)) {
  command = `"${venvPythonWin}"`;
} else if (fs.existsSync(venvPythonUnix)) {
  command = `"${venvPythonUnix}"`;
} else if (fs.existsSync(envPythonWin)) {
  command = `"${envPythonWin}"`;
} else if (fs.existsSync(envPythonUnix)) {
  command = `"${envPythonUnix}"`;
}

console.log(`[Desktop Orchestrator] Ejecutando en: ${desktopDir}`);
console.log(`[Desktop Orchestrator] Comando: ${command} ${args.join(' ')}`);

const proc = spawn(command, args, {
  cwd: desktopDir,
  stdio: 'inherit',
  shell: true
});

proc.on('exit', (code) => {
  process.exit(code || 0);
});
