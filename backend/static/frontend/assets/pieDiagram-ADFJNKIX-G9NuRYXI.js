import{g as j,s as q,a as H,b as Z,q as J,p as K,_ as p,l as F,c as Q,D as X,H as Y,O as ee,e as te,y as ae,E as re}from"./mermaid.core-F3dSbIB5.js";import{p as ne}from"./chunk-4BX2VUAB-DPpowxvl.js";import{p as ie}from"./treemap-KMMF4GRG-lTobm3QT.js";import{d as I}from"./arc-DTzU-hmE.js";import{o as se}from"./ordinal-DILIJJjt.js";import{a as S,t as z,n as le}from"./string-GBVq1Gk0.js";import"./index-roHVKWBY.js";import"./min-3_V0NlMf.js";import"./_baseUniq-BNoQzRSK.js";import"./init-Dmth1JHB.js";function oe(e,a){return a<e?-1:a>e?1:a>=e?0:NaN}function ce(e){return e}function ue(){var e=ce,a=oe,f=null,y=S(0),s=S(z),o=S(0);function l(t){var n,c=(t=le(t)).length,d,x,h=0,u=new Array(c),i=new Array(c),v=+y.apply(this,arguments),w=Math.min(z,Math.max(-z,s.apply(this,arguments)-v)),m,C=Math.min(Math.abs(w)/c,o.apply(this,arguments)),$=C*(w<0?-1:1),g;for(n=0;n<c;++n)(g=i[u[n]=n]=+e(t[n],n,t))>0&&(h+=g);for(a!=null?u.sort(function(A,D){return a(i[A],i[D])}):f!=null&&u.sort(function(A,D){return f(t[A],t[D])}),n=0,x=h?(w-c*$)/h:0;n<c;++n,v=m)d=u[n],g=i[d],m=v+(g>0?g*x:0)+$,i[d]={data:t[d],index:n,value:g,startAngle:v,endAngle:m,padAngle:C};return i}return l.value=function(t){return arguments.length?(e=typeof t=="function"?t:S(+t),l):e},l.sortValues=function(t){return arguments.length?(a=t,f=null,l):a},l.sort=function(t){return arguments.length?(f=t,a=null,l):f},l.startAngle=function(t){return arguments.length?(y=typeof t=="function"?t:S(+t),l):y},l.endAngle=function(t){return arguments.length?(s=typeof t=="function"?t:S(+t),l):s},l.padAngle=function(t){return arguments.length?(o=typeof t=="function"?t:S(+t),l):o},l}var pe=re.pie,G={sections:new Map,showData:!1},T=G.sections,N=G.showData,de=structuredClone(pe),ge=p(()=>structuredClone(de),"getConfig"),fe=p(()=>{T=new Map,N=G.showData,ae()},"clear"),me=p(({label:e,value:a})=>{if(a<0)throw new Error(`"${e}" has invalid value: ${a}. Negative values are not allowed in pie charts. All slice values must be >= 0.`);T.has(e)||(T.set(e,a),F.debug(`added new section: ${e}, with value: ${a}`))},"addSection"),he=p(()=>T,"getSections"),ve=p(e=>{N=e},"setShowData"),Se=p(()=>N,"getShowData"),L={getConfig:ge,clear:fe,setDiagramTitle:K,getDiagramTitle:J,setAccTitle:Z,getAccTitle:H,setAccDescription:q,getAccDescription:j,addSection:me,getSections:he,setShowData:ve,getShowData:Se},ye=p((e,a)=>{ne(e,a),a.setShowData(e.showData),e.sections.map(a.addSection)},"populateDb"),xe={parse:p(async e=>{const a=await ie("pie",e);F.debug(a),ye(a,L)},"parse")},we=p(e=>`
  .pieCircle{
    stroke: ${e.pieStrokeColor};
    stroke-width : ${e.pieStrokeWidth};
    opacity : ${e.pieOpacity};
  }
  .pieOuterCircle{
    stroke: ${e.pieOuterStrokeColor};
    stroke-width: ${e.pieOuterStrokeWidth};
    fill: none;
  }
  .pieTitleText {
    text-anchor: middle;
    font-size: ${e.pieTitleTextSize};
    fill: ${e.pieTitleTextColor};
    font-family: ${e.fontFamily};
  }
  .slice {
    font-family: ${e.fontFamily};
    fill: ${e.pieSectionTextColor};
    font-size:${e.pieSectionTextSize};
    // fill: white;
  }
  .legend text {
    fill: ${e.pieLegendTextColor};
    font-family: ${e.fontFamily};
    font-size: ${e.pieLegendTextSize};
  }
`,"getStyles"),Ae=we,De=p(e=>{const a=[...e.values()].reduce((s,o)=>s+o,0),f=[...e.entries()].map(([s,o])=>({label:s,value:o})).filter(s=>s.value/a*100>=1).sort((s,o)=>o.value-s.value);return ue().value(s=>s.value)(f)},"createPieArcs"),Ce=p((e,a,f,y)=>{F.debug(`rendering pie chart
`+e);const s=y.db,o=Q(),l=X(s.getConfig(),o.pie),t=40,n=18,c=4,d=450,x=d,h=Y(a),u=h.append("g");u.attr("transform","translate("+x/2+","+d/2+")");const{themeVariables:i}=o;let[v]=ee(i.pieOuterStrokeWidth);v??=2;const w=l.textPosition,m=Math.min(x,d)/2-t,C=I().innerRadius(0).outerRadius(m),$=I().innerRadius(m*w).outerRadius(m*w);u.append("circle").attr("cx",0).attr("cy",0).attr("r",m+v/2).attr("class","pieOuterCircle");const g=s.getSections(),A=De(g),D=[i.pie1,i.pie2,i.pie3,i.pie4,i.pie5,i.pie6,i.pie7,i.pie8,i.pie9,i.pie10,i.pie11,i.pie12];let E=0;g.forEach(r=>{E+=r});const O=A.filter(r=>(r.data.value/E*100).toFixed(0)!=="0"),b=se(D);u.selectAll("mySlices").data(O).enter().append("path").attr("d",C).attr("fill",r=>b(r.data.label)).attr("class","pieCircle"),u.selectAll("mySlices").data(O).enter().append("text").text(r=>(r.data.value/E*100).toFixed(0)+"%").attr("transform",r=>"translate("+$.centroid(r)+")").style("text-anchor","middle").attr("class","slice"),u.append("text").text(s.getDiagramTitle()).attr("x",0).attr("y",-400/2).attr("class","pieTitleText");const W=[...g.entries()].map(([r,M])=>({label:r,value:M})),k=u.selectAll(".legend").data(W).enter().append("g").attr("class","legend").attr("transform",(r,M)=>{const R=n+c,B=R*W.length/2,V=12*n,U=M*R-B;return"translate("+V+","+U+")"});k.append("rect").attr("width",n).attr("height",n).style("fill",r=>b(r.label)).style("stroke",r=>b(r.label)),k.append("text").attr("x",n+c).attr("y",n-c).text(r=>s.getShowData()?`${r.label} [${r.value}]`:r.label);const _=Math.max(...k.selectAll("text").nodes().map(r=>r?.getBoundingClientRect().width??0)),P=x+t+n+c+_;h.attr("viewBox",`0 0 ${P} ${d}`),te(h,d,P,l.useMaxWidth)},"draw"),$e={draw:Ce},We={parser:xe,db:L,renderer:$e,styles:Ae};export{We as diagram};
