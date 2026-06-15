import * as art from '@oai/artifact-tool';
const p = art.Presentation.create({slideSize:{width:1280,height:720}});
const s = p.slides.add();
console.log('compose object', s.compose);
console.log('compose auto', s.compose.auto);
