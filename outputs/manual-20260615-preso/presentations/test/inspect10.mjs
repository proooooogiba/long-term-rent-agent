import * as art from '@oai/artifact-tool';
for (const key of ['panel','grid']) {
  console.log('FN', key, art[key].toString().slice(0,1000).replace(/\n/g,' '));
}
