import * as art from '@oai/artifact-tool';
for (const key of ['text','shape','image','panel','slide','line','connector','grid','stack','hstack','vstack']) {
  if (typeof art[key] === 'function') {
    console.log('FN', key, art[key].toString().slice(0,300).replace(/\n/g,' '));
  } else if (art[key] !== undefined) {
    console.log('VAL', key, typeof art[key]);
  }
}
