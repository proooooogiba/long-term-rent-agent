import * as art from '@oai/artifact-tool';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const assetDir = path.dirname(fileURLToPath(import.meta.url));
const pngPath = path.join(assetDir, 'search_ui.png');
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
