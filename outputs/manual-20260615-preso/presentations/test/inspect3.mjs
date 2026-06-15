import * as art from '@oai/artifact-tool';
const p = art.Presentation.create({slideSize:{width:1280,height:720}});
console.log('slides proto', Object.getOwnPropertyNames(Object.getPrototypeOf(p.slides)).sort().join(','));
console.log('presentation proto', Object.getOwnPropertyNames(Object.getPrototypeOf(p)).sort().join(','));
