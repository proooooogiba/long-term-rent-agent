import * as art from '@oai/artifact-tool';
const p = art.Presentation.create({slideSize:{width:1280,height:720}});
const s = p.slides.add();
console.log('slide proto', Object.getOwnPropertyNames(Object.getPrototypeOf(s)).sort().join(','));
console.log('compose keys', Object.keys(p.compose || {}).join(','));
