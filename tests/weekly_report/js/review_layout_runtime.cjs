const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const view=fs.readFileSync('scripts/weekly_report/review/review-view.js','utf8');
const template=fs.readFileSync('scripts/weekly_report/template/report_v2_template.html','utf8');
// Execute the actual sidebar toggle with access ONLY to the shell and button.
// Touching/replacing a CE, notes, drafts or any network integration fails here.
const label={textContent:'Collapse sidebar'};
const button={attrs:{},setAttribute(k,v){this.attrs[k]=v;},querySelector(s){assert.equal(s,'.rail-toggle-label');return label;}};
const shell={classList:{toggle(k){assert.equal(k,'rail-collapsed');this[k]=!this[k];return this[k];}}};
let scheduled=0;
const c=vm.createContext({document:{querySelector(s){assert.equal(s,'.shell');return shell;},getElementById(s){assert.equal(s,'rail-toggle');return button;}},scheduleFloatingHeader(){scheduled++;}});
vm.runInContext(template.slice(template.indexOf('      function toggleReportSidebar()'),template.indexOf('      function initReportSidebar()')),c);
c.toggleReportSidebar();
assert.equal(shell.classList['rail-collapsed'],true);
assert.equal(button.attrs['aria-expanded'],'false');assert.equal(button.attrs['aria-label'],'Expand sidebar');assert.equal(label.textContent,'Expand sidebar');
c.toggleReportSidebar();
assert.equal(shell.classList['rail-collapsed'],false);
assert.equal(button.attrs['aria-expanded'],'true');assert.equal(button.title,'Collapse sidebar');assert.equal(label.textContent,'Collapse sidebar');
assert.equal(scheduled,2);
assert.match(template,/aria-controls="report-sidebar"/);
assert.match(template,/addEventListener\('click',toggleReportSidebar\)/);
assert.match(template,/grid-template-columns:68px minmax\(0,1fr\)/);
assert.match(template,/Seasonality adjustments will be shown here\./);
assert.doesNotMatch(template,/No seasonality adjustments currently set for this market/);
assert.doesNotMatch(view,/rv-toggle-notes|auditCollapsed|rv-audit-panel|toggleAuditPanel/);
assert.doesNotMatch(fs.readFileSync('scripts/weekly_report/review/review-view.css','utf8'),/rv-notes-collapsed|rv-panel-toggle/);

// The floating header follows its actual scrollport, including narrow/clipped
// panes, while ordinary report tables and modal drawers retain their boundaries.
const bounds=vm.createContext({innerHeight:800,innerWidth:1200});
vm.runInContext(template.slice(template.indexOf('      function floatingTableBounds('),template.indexOf('      function updateFloatingHeader()')),bounds);
function check(rect,expected){const table={closest:s=>{assert.equal(s,'.rv-embedded-data');return rect?{getBoundingClientRect:()=>rect}:null;}};assert.deepEqual({...bounds.floatingTableBounds(table,null)},expected);}
check({top:164,bottom:754,left:174,right:720},{top:164,bottom:754,left:174,right:720});
check({top:-24,bottom:354,left:-10,right:500},{top:0,bottom:354,left:0,right:500});
check({top:170,bottom:1100,left:174,right:1400},{top:170,bottom:800,left:174,right:1200});
check(null,{top:0,bottom:800,left:0,right:1200});
assert.equal(bounds.floatingTableBounds({closest:()=>null},{querySelector:()=>({getBoundingClientRect:()=>({bottom:112})})}).top,112);
assert.match(template,/bounds\.bottom>boundary\+height/);
assert.match(template,/top:`\$\{bounds\.top\}px`/);
assert.match(template,/floatingHead\.scrollLeft=wrap\.scrollLeft\+left-box\.left/);
console.log('Mini Audit layout runtime regressions passed');
