const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

const backendDir = path.join(__dirname, '..', 'Backend');
let command = 'python';
const defaultArgs = ['main:app', '--reload', '--host', '0.0.0.0', '--port', '8000'];
let args = ['-m', 'uvicorn', ...defaultArgs];

// Posibles rutas del ejecutable de uvicorn en el entorno virtual
const venvUvicornWin = path.join(backendDir, '.venv', 'Scripts', 'uvicorn.exe');
const venvUvicornUnix = path.join(backendDir, '.venv', 'bin', 'uvicorn');
const envUvicornWin = path.join(backendDir, 'env', 'Scripts', 'uvicorn.exe');
const envUvicornUnix = path.join(backendDir, 'env', 'bin', 'uvicorn');

if (fs.existsSync(venvUvicornWin)) {
  command = `"${venvUvicornWin}"`;
  args = defaultArgs;
} else if (fs.existsSync(venvUvicornUnix)) {
  command = `"${venvUvicornUnix}"`;
  args = defaultArgs;
} else if (fs.existsSync(envUvicornWin)) {
  command = `"${envUvicornWin}"`;
  args = defaultArgs;
} else if (fs.existsSync(envUvicornUnix)) {
  command = `"${envUvicornUnix}"`;
  args = defaultArgs;
}

console.log(`[Backend Orchestrator] Ejecutando en: ${backendDir}`);
console.log(`[Backend Orchestrator] Comando: ${command} ${args.join(' ')}`);

const proc = spawn(command, args, {
  cwd: backendDir,
  stdio: 'inherit',
  shell: true
});

proc.on('exit', (code) => {
  process.exit(code || 0);
});
