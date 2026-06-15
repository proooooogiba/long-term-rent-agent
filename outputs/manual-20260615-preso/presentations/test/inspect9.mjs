import * as art from '@oai/artifact-tool';
for (const key of ['fixed','auto','fr','grow','hug','wrap']) {
  console.log('FN', key, art[key].toString().slice(0,240).replace(/\n/g,' '));
}
