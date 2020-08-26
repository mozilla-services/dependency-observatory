!function(e,t){"object"==typeof exports&&"undefined"!=typeof module?t(exports):"function"==typeof define&&define.amd?define(["exports"],t):t((e=e||self).vega=e.vega||{})}(this,(function(e){"use strict";var t={NaN:NaN,E:Math.E,LN2:Math.LN2,LN10:Math.LN10,LOG2E:Math.LOG2E,LOG10E:Math.LOG10E,PI:Math.PI,SQRT1_2:Math.SQRT1_2,SQRT2:Math.SQRT2,MIN_VALUE:Number.MIN_VALUE,MAX_VALUE:Number.MAX_VALUE},n={"*":(e,t)=>e*t,"+":(e,t)=>e+t,"-":(e,t)=>e-t,"/":(e,t)=>e/t,"%":(e,t)=>e%t,">":(e,t)=>e>t,"<":(e,t)=>e<t,"<=":(e,t)=>e<=t,">=":(e,t)=>e>=t,"==":(e,t)=>e==t,"!=":(e,t)=>e!=t,"===":(e,t)=>e===t,"!==":(e,t)=>e!==t,"&":(e,t)=>e&t,"|":(e,t)=>e|t,"^":(e,t)=>e^t,"<<":(e,t)=>e<<t,">>":(e,t)=>e>>t,">>>":(e,t)=>e>>>t},a={"+":e=>+e,"-":e=>-e,"~":e=>~e,"!":e=>!e};const r=Array.prototype.slice,s=(e,t,n)=>{const a=n?n(t[0]):t[0];return a[e].apply(a,r.call(t,1))};var o={isNaN:Number.isNaN,isFinite:Number.isFinite,abs:Math.abs,acos:Math.acos,asin:Math.asin,atan:Math.atan,atan2:Math.atan2,ceil:Math.ceil,cos:Math.cos,exp:Math.exp,floor:Math.floor,log:Math.log,max:Math.max,min:Math.min,pow:Math.pow,random:Math.random,round:Math.round,sin:Math.sin,sqrt:Math.sqrt,tan:Math.tan,clamp:(e,t,n)=>Math.max(t,Math.min(n,e)),now:Date.now,utc:Date.UTC,datetime:(e,t,n,a,r,s,o)=>new Date(e,t||0,null!=n?n:1,a||0,r||0,s||0,o||0),date:e=>new Date(e).getDate(),day:e=>new Date(e).getDay(),year:e=>new Date(e).getFullYear(),month:e=>new Date(e).getMonth(),hours:e=>new Date(e).getHours(),minutes:e=>new Date(e).getMinutes(),seconds:e=>new Date(e).getSeconds(),milliseconds:e=>new Date(e).getMilliseconds(),time:e=>new Date(e).getTime(),timezoneoffset:e=>new Date(e).getTimezoneOffset(),utcdate:e=>new Date(e).getUTCDate(),utcday:e=>new Date(e).getUTCDay(),utcyear:e=>new Date(e).getUTCFullYear(),utcmonth:e=>new Date(e).getUTCMonth(),utchours:e=>new Date(e).getUTCHours(),utcminutes:e=>new Date(e).getUTCMinutes(),utcseconds:e=>new Date(e).getUTCSeconds(),utcmilliseconds:e=>new Date(e).getUTCMilliseconds(),length:e=>e.length,join:function(){return s("join",arguments)},indexof:function(){return s("indexOf",arguments)},lastindexof:function(){return s("lastIndexOf",arguments)},slice:function(){return s("slice",arguments)},reverse:e=>e.slice().reverse(),parseFloat:parseFloat,parseInt:parseInt,upper:e=>String(e).toUpperCase(),lower:e=>String(e).toLowerCase(),substring:function(){return s("substring",arguments,String)},split:function(){return s("split",arguments,String)},replace:function(){return s("replace",arguments,String)},trim:e=>String(e).trim(),regexp:RegExp,test:(e,t)=>RegExp(e).test(t)};const i={Literal:(e,t)=>t.value,Identifier:(e,n)=>{const a=n.name;return e.memberDepth>0?a:"datum"===a?e.datum:"event"===a?e.event:"item"===a?e.item:t[a]||e.params["$"+a]},MemberExpression:(e,t)=>{const n=!t.computed,a=e(t.object);n&&(e.memberDepth+=1);const r=e(t.property);return n&&(e.memberDepth-=1),a[r]},CallExpression:(e,t)=>{let n=t.callee.name,a=t.arguments;return n.startsWith("_")&&(n=n.slice(1)),"if"===n?e(a[0])?e(a[1]):e(a[2]):(e.fn[n]||o[n]).apply(e.fn,a.map(e))},ArrayExpression:(e,t)=>t.elements.map(e),BinaryExpression:(e,t)=>n[t.operator](e(t.left),e(t.right)),UnaryExpression:(e,t)=>a[t.operator](e(t.argument)),ConditionalExpression:(e,t)=>e(t.test)?e(t.consequent):e(t.alternate),LogicalExpression:(e,t)=>"&&"===t.operator?e(t.left)&&e(t.right):e(t.left)||e(t.right),ObjectExpression:(e,t)=>t.properties.reduce((t,n)=>{e.memberDepth+=1;const a=e(n.key);return e.memberDepth-=1,t[a]=e(n.value),t},{})};function u(e,t,n,a,r,s){const o=e=>i[e.type](o,e);return o.memberDepth=0,o.fn=t,o.params=n,o.datum=a,o.event=r,o.item=s,o(e)}var c={operator(e,t){const n=t.ast,a=e.functions;return e=>u(n,a,e)},parameter(e,t){const n=t.ast,a=e.functions;return(e,t)=>u(n,a,t,e)},event(e,t){const n=t.ast,a=e.functions;return e=>u(n,a,void 0,void 0,e)},handler(e,t){const n=t.ast,a=e.functions;return(e,t)=>{const r=t.item&&t.item.datum;return u(n,a,e,r,t)}},encode(e,t){const{marktype:n,channels:a}=t,r=e.functions,s="group"===n||"image"===n||"rect"===n;return(e,t)=>{const o=e.datum;let i,c=0;for(const n in a)i=u(a[n].ast,r,t,o,void 0,e),e[n]!==i&&(e[n]=i,c=1);return"rule"!==n&&function(e,t,n){let a;t.x2&&(t.x?(n&&e.x>e.x2&&(a=e.x,e.x=e.x2,e.x2=a),e.width=e.x2-e.x):e.x=e.x2-(e.width||0)),t.xc&&(e.x=e.xc-(e.width||0)/2),t.y2&&(t.y?(n&&e.y>e.y2&&(a=e.y,e.y=e.y2,e.y2=a),e.height=e.y2-e.y):e.y=e.y2-(e.height||0)),t.yc&&(e.y=e.yc-(e.height||0)/2)}(e,a,s),c}}};e.expressionInterpreter=c,Object.defineProperty(e,"__esModule",{value:!0})}));