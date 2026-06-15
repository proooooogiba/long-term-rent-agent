import * as art from '@oai/artifact-tool';
console.log('FN text', art.text.toString().slice(0,1000).replace(/\n/g,' '));
console.log('FN image', art.image.toString().slice(0,1000).replace(/\n/g,' '));
