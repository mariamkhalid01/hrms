import {createRequire} from 'node:module';
import {writeFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
const require=createRequire('C:/Program Files/WindowsApps/OpenAI.CodexPrimaryRuntime.v26-1104-2876-0_26.1104.2876.0_x64__3k8sg7r9htsxt/dependencies/node/node_modules/');
const {chromium}=require('playwright');
const browser=await chromium.launch({channel:'msedge',headless:true});
const page=await browser.newPage({viewport:{width:1440,height:1050}});
const id='cbd64c13-9b05-42e0-86d2-c0cd2fba1a12';
page.setDefaultTimeout(20000);
const checks={},errors=[];let failure;
const check=(name,value)=>{checks[name]=!!value;assert(value,name)};
page.on('pageerror',e=>errors.push(e.message));
const api=async path=>{const r=await page.request.get(`http://127.0.0.1:5173/api/v1/datasets/${id}${path}`);assert(r.ok());return r.json()};
const go=async(route,selector)=>{await page.goto(`http://127.0.0.1:5173/${route}?dataset=${id}`);await page.locator(selector).first().waitFor();};
try{
 await go('process-explorer','.pe-task');const discovery=await api('/discovery');
 for(const process of discovery.processes){
  await page.getByLabel('Select process',{exact:true}).selectOption(process.id);
  const paths=(await api(`/analytics/processes/${process.id}/variants?limit=4`)).items;
  await page.waitForFunction(labels=>JSON.stringify([...document.querySelectorAll('.pe-task > strong')].map(x=>x.textContent))===JSON.stringify(labels),paths[0].activity_sequence);
  check(`${process.name}_real_first_path`,true);
  check(`${process.name}_real_path_count`,await page.locator('.ex-path-row').count()===paths.length);
  check(`${process.name}_process_totals`,(await page.getByLabel('Selected process totals').innerText()).includes(process.case_count.toLocaleString()));
  const bar=await page.locator('.ex-path-row').first().locator('.ex-path-track > span').evaluate(x=>Number.parseFloat(x.style.width));
  check(`${process.name}_actual_bar_percentage`,Math.abs(bar-paths[0].percentage)<0.001);
  if(paths.length>1){await page.locator('.ex-path-row').nth(1).click();await page.waitForFunction(labels=>JSON.stringify([...document.querySelectorAll('.pe-task > strong')].map(x=>x.textContent))===JSON.stringify(labels),paths[1].activity_sequence);check(`${process.name}_select_path_changes_map`,true);}
 }
 await page.getByRole('button',{name:'Next paths',exact:true}).click();await page.getByRole('button',{name:/Show path 5:/}).waitFor();
 const recruitment=discovery.processes.at(-1);const next=(await api(`/analytics/processes/${recruitment.id}/variants?offset=4&limit=4`)).items;
 await page.waitForFunction(labels=>JSON.stringify([...document.querySelectorAll('.pe-task > strong')].map(x=>x.textContent))===JSON.stringify(labels),next[0].activity_sequence);
 check('paths_pagination_actual_sequence',true);
 await page.getByRole('button',{name:'All paths',exact:true}).click();await page.waitForFunction(n=>document.querySelectorAll('.pe-task').length===n,recruitment.activities.length);
 check('all_paths_actual_nodes',true);
 check('all_paths_actual_edges',await page.locator('.react-flow__edge').count()===recruitment.transitions.length+recruitment.start_activities.length+recruitment.end_activities.length);
 await page.getByRole('button',{name:'Time',exact:true}).click();await page.waitForFunction(()=>document.querySelector('.pe-task-metric small')?.textContent==='avg. processing');check('time_mode_actual_processing',true);
 await page.getByRole('button',{name:'Rework',exact:true}).click();await page.waitForFunction(()=>document.querySelector('.pe-task-metric small')?.textContent==='cases repeated');check('rework_mode_actual_repeats',true);
 await page.getByRole('button',{name:'Map settings',exact:true}).click();await page.getByLabel('Minimum route count',{exact:true}).fill('10');
 await page.waitForFunction(n=>document.querySelectorAll('.react-flow__edge').length===n,recruitment.transitions.filter(x=>x.frequency>=10).length+recruitment.start_activities.length+recruitment.end_activities.length);check('route_filter_uses_real_counts',true);
 await page.getByRole('button',{name:'Map settings',exact:true}).click();
 await page.locator('.ex-gap-row').first().click();await page.getByRole('dialog').waitFor();check('timing_chart_opens_evidence',await page.getByRole('heading',{name:'Waiting between these steps',exact:true}).isVisible());await page.keyboard.press('Escape');
 await page.getByRole('button',{name:'Fit diagram',exact:true}).click();check('fit_control_operates',true);
 await page.getByRole('button',{name:'Frequency',exact:true}).click();
 const first=discovery.processes[0];await page.getByLabel('Select process',{exact:true}).selectOption(first.id);await page.getByRole('button',{name:'Selected path',exact:true}).click();await page.locator('.ex-path-row').first().waitFor();
 await page.waitForFunction(()=>document.querySelector('.ex-path-row')?.getAttribute('aria-pressed')==='true');
 check('bounded_canvas',await page.locator('.pe-flow-canvas').evaluate(x=>x.getBoundingClientRect().height<=650));
 await page.screenshot({path:'work/reference-explorer-desktop.png',fullPage:true});
 for(const width of [1920,1440,1200,1100,961,960,768,390,320]){
  await page.setViewportSize({width,height:1000});
  for(const [route,selector] of [['overview','.executive-dashboard'],['process-explorer','.pe-task'],['bottlenecks','.finding-summary'],['variants','.path-comparison-row'],['recommendations','.recommendation-card'],['cases','.case-list-item']]){
   await go(route,selector);
   check(`${width}_${route}_fits`,await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
   check(`${width}_${route}_content_keeps_sidebar_space`,await page.locator('.workspace').evaluate(x=>Math.abs(x.getBoundingClientRect().right-innerWidth)<1));
   if([1440,390].includes(width)&&['overview','process-explorer','variants','bottlenecks','recommendations'].includes(route))await page.screenshot({path:`work/reference-${route}-${width}.png`,fullPage:true});
  }
 }
 await page.goto('http://127.0.0.1:5173/overview');await page.getByRole('heading',{name:'Start with an HR event log'}).waitFor();check('fresh_session_remains_empty',true);
 check('no_browser_errors',errors.length===0);
}catch(e){failure=String(e);console.error(page.url(),(await page.locator('body').innerText()).slice(0,2200));await page.screenshot({path:'work/reference-ui-failure.png',fullPage:true});throw e}
finally{const report={completed:!failure,failure,passed:Object.values(checks).filter(Boolean).length,checks,errors};await writeFile('work/reference-dashboard-report.json',JSON.stringify(report,null,2));console.log(JSON.stringify({completed:!failure,failure,passed:report.passed,errors},null,2));await browser.close()}

