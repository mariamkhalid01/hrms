import {createRequire} from 'node:module';
import {writeFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
const require=createRequire('C:/Program Files/WindowsApps/OpenAI.CodexPrimaryRuntime.v26-1104-2876-0_26.1104.2876.0_x64__3k8sg7r9htsxt/dependencies/node/node_modules/');
const {chromium}=require('playwright');
const browser=await chromium.launch({channel:'msedge',headless:true});
const page=await browser.newPage({viewport:{width:1440,height:1000}});
const id='cbd64c13-9b05-42e0-86d2-c0cd2fba1a12';
const errors=[],checks={};let failure;
const check=(n,v)=>{checks[n]=!!v;assert(v,n)};
page.on('pageerror',e=>errors.push(e.message));
try{
 const r=await page.request.get(`http://127.0.0.1:5173/api/v1/datasets/${id}/analytics`);const data=await r.json();
 await page.goto(`http://127.0.0.1:5173/overview?dataset=${id}`);await page.locator('.dashboard-finding').first().waitFor();
 check('four_kpis',await page.locator('.dashboard-kpis > div').count()===4);
 const kpis=await page.locator('.dashboard-kpis').innerText();check('actual_kpi_totals',kpis.includes(data.total_cases.toLocaleString())&&kpis.includes(data.total_events.toLocaleString())&&kpis.includes(data.process_count.toLocaleString()));
 check('three_priority_findings',await page.locator('.dashboard-finding').count()===3);
 check('all_process_rows',await page.locator('.dashboard-process-table tbody tr').count()===data.process_count);
 check('compact_dashboard',await page.locator('.executive-dashboard').evaluate(el=>el.getBoundingClientRect().height<1050));
 check('methodology_collapsed',await page.locator('.dashboard-methods').getAttribute('open')===null);
 for(const width of [1440,1100,390]){
  await page.setViewportSize({width,height:1000});await page.waitForTimeout(200);
  check(`${width}_no_page_overflow`,await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await page.screenshot({path:`work/executive-overview-${width}.png`,fullPage:true});
 }
 await page.setViewportSize({width:1440,height:1000});
 const href=await page.locator('.dashboard-process-table tbody th a').first().getAttribute('href');
 check('process_drilldown_keeps_dataset_and_process',href.includes(`dataset=${id}`)&&href.includes('process='));
 await page.locator('.dashboard-methods summary').click();check('closure_semantics_preserved',(await page.locator('.dashboard-methods').innerText()).includes('it does not mean success'));
 await page.route('**/analytics/findings?**',route=>route.abort('connectionrefused'));
 await page.reload();await page.getByRole('alert').filter({hasText:'Unable to load this view'}).waitFor();check('findings_error_explained',true);
 await page.unroute('**/analytics/findings?**');await page.getByRole('button',{name:'Retry',exact:true}).click();await page.locator('.dashboard-finding').first().waitFor();check('findings_retry_recovers',true);
 await page.goto('http://127.0.0.1:5173/overview');await page.getByRole('heading',{name:'Start with an HR event log'}).waitFor();check('fresh_session_empty',true);
 check('no_javascript_errors',errors.length===0);
}catch(e){failure=String(e);throw e}finally{const report={completed:!failure,failure,checks,errors,passed:Object.values(checks).filter(Boolean).length};await writeFile('work/executive-overview-checks.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report));await browser.close()}
