import { spawn } from 'child_process';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const queryScript = path.join(__dirname, 'query.py');

function runPython(args, stdinData = null) {
    return new Promise((resolve, reject) => {
        const proc = spawn('python3', [queryScript, ...args], {
            stdio: ['pipe', 'pipe', 'pipe'],
        });
        let stdout = '';
        let stderr = '';
        proc.stdout.on('data', (data) => { stdout += data; });
        proc.stderr.on('data', (data) => { stderr += data; });
        proc.on('close', (code) => {
            if (code !== 0) {
                reject(new Error(`Python exited ${code}: ${stderr}`));
            } else {
                try {
                    resolve(JSON.parse(stdout));
                } catch (e) {
                    reject(new Error(`Invalid JSON: ${stdout}`));
                }
            }
        });
        if (stdinData) {
            proc.stdin.write(JSON.stringify(stdinData));
        }
        proc.stdin.end();
    });
}

export const info = {
    id: 'phoenix-bridge',
    name: 'Phoenix Memory Bridge',
    description: 'Connects SillyTavern to Phoenix v2 memory database',
};

export async function init(router) {
    router.get('/test', (req, res) => {
        console.log('[phoenix-bridge] /test hit');
        res.json({ ok: true, timestamp: Date.now() });
    });

    router.get('/memory', async (req, res) => {
        try {
            console.log('[phoenix-bridge] /memory hit', req.query);
            const agent = req.query.agent || '';
            const cmd = req.query.cmd || 'salient';
            const query = req.query.q || '';
            const limit = parseInt(req.query.limit) || 5;
            const results = await runPython([cmd, agent, query, String(limit)]);
            console.log('[phoenix-bridge] results type:', typeof results, Array.isArray(results));
            const jsonStr = JSON.stringify(results);
            console.log('[phoenix-bridge] json length:', jsonStr.length);
            res.setHeader('Content-Type', 'application/json');
            res.send(jsonStr);
        } catch (error) {
            console.error('[phoenix-bridge]', error.message);
            res.status(500).json({ error: error.message });
        }
    });

    router.post('/memory', async (req, res) => {
        try {
            const result = await runPython(['add'], req.body);
            res.json(result);
        } catch (error) {
            console.error('[phoenix-bridge]', error.message);
            res.status(500).json({ error: error.message });
        }
    });

    console.log('[phoenix-bridge] Plugin loaded. Routes: /api/plugins/phoenix-bridge/memory');
}
