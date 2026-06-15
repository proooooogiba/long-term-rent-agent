import * as art from '@oai/artifact-tool';
import fs from 'node:fs';
const pngPath = '/Users/iopogiba/Documents/HSE/Module 3/AI AGENT/final_work/outputs/manual-20260615-relocation-defense/presentations/relocation-agent-deck/assets/search_ui.png';
const buf = fs.readFileSync(pngPath);
const dataUrl = `data:image/png;base64,${buf.toString('base64')}`;
const vars = [
  { source: { path: pngPath } },
  { source: { data: dataUrl } },
  { source: { url: dataUrl } },
  { source: { bytes: buf } },
  { path: pngPath },
  { data: dataUrl },
  { url: dataUrl },
];
for (const v of vars) {
  try {
    const out = art.image(v);
    console.log(JSON.stringify({ input: Object.keys(v), source: out.source }, null, 2));
  } catch (e) {
    console.log('ERR', Object.keys(v), e.message);
  }
}
