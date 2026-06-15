import * as art from '@oai/artifact-tool';
const p = art.Presentation.create({slideSize:{width:1280,height:720}});
console.log(p.compose.toString().slice(0,1000).replace(/\n/g,' '));
console.log('slides.add', p.slides.add.toString().slice(0,600).replace(/\n/g,' '));
