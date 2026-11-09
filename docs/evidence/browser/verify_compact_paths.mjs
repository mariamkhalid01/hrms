import {createRequire} from 'node:module';
import {writeFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
const require=createRequire('C:/Program Files/WindowsApps/OpenAI.CodexPrimaryRuntime.v26-1104-2876-0_26.1104.2876.0_x64__3k8sg7r9htsxt/dependencies/node/node_modules/');
const {chromium}=require('playwright');
const browser=await chromium.launch({channel:'msedge',headless:true});
const page=await browser.newPage({viewport:{width:1440,height:1000}});
page.setDefaultTimeout(20000);
const dataset='cbd64c13-9b05-42e0-86d2-c0cd2fba1a12';
const checks={}, errors=[];let failure;
const check=(name,value)=>{checks[name]=!!value;assert(value,name)};
page.on('pageerror',e=>errors.push(e.message));
const api=async path=>{const r=await page.request.get(`http://127.0.0.1:5173/api/v1/datasets/${dataset}${path}`);assert(r.ok());return r.json()};
try{
 await page.goto(`http://127.0.0.1:5173/variants?dataset=${dataset}`);await page.locator('.path-comparison-row').first().waitFor();
 const analytics=await api('/analytics');
 for(const process of analytics.processes){
  const variants=await api(`/analytics/processes/${process.id}/variants?limit=8`);
  await page.getByLabel('Process',{exact:true}).selectOption(process.id);
  await page.waitForFunction(expected=>document.querySelector('.path-comparison-name > small')?.textContent===`Last step: ${expected}`,variants.items[0].activity_sequence.at(-1));
  await page.waitForFunction(n=>document.querySelectorAll('.path-comparison-row').length===n,variants.items.length);
  check(`${process.name}_actual_row_count`,await page.locator('.path-comparison-row').count()===variants.items.length);
  check(`${process.name}_actual_case_counts`,JSON.stringify(await page.locator('.path-comparison-number > strong').allTextContents())===JSON.stringify(variants.items.map(v=>v.case_count.toLocaleString())));
  check(`${process.name}_actual_bar_widths`,await page.locator('.paths-frequency-track > span').evaluateAll((els,values)=>els.every((el,i)=>Math.abs(parseFloat(el.style.width)-values[i])<.001),variants.items.map(v=>v.percentage)));
  await page.getByRole('button',{name:'View full path 1',exact:true}).click();await page.getByRole('dialog').waitFor();
  check(`${process.name}_actual_sequence`,JSON.stringify(await page.locator('.path-step-content > span').allTextContents())===JSON.stringify(variants.items[0].activity_sequence));
  check(`${process.name}_case_drilldown`,(await page.getByRole('dialog').getByRole('link',{name:/Explore the .* cases on this path/}).getAttribute('href')).includes(variants.items[0].id));
  await page.keyboard.press('Escape');
 }
 const nextResponse=page.waitForResponse(r=>r.url().includes('/variants?offset=8')&&r.ok());
 await page.getByRole('button',{name:'Next',exact:true}).click();await nextResponse;await page.getByRole('button',{name:'View full path 9',exact:true}).waitFor();
 check('actual_pagination_next',await page.getByRole('button',{name:'View full path 9',exact:true}).isVisible());
 const previousResponse=page.waitForResponse(r=>r.url().includes('/variants?offset=0')&&r.ok());
 await page.getByRole('button',{name:'Previous',exact:true}).click();await previousResponse;await page.getByRole('button',{name:'View full path 1',exact:true}).waitFor();
 for(const width of [1440,1100,961,768,390,320]){
  await page.setViewportSize({width,height:1000});
  check(`${width}_no_overflow`,await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  if([1440,1100,390].includes(width))await page.screenshot({path:`work/compact-paths-${width}.png`,fullPage:true});
 }
 await page.getByRole('button',{name:'View full path 1',exact:true}).click();await page.getByRole('dialog').waitFor();
 check('mobile_dialog_fits',await page.getByRole('dialog').evaluate(el=>el.scrollWidth<=el.clientWidth&&el.getBoundingClientRect().right<=innerWidth));
 check('no_browser_errors',errors.length===0);
}catch(e){failure=String(e);await page.screenshot({path:'work/compact-paths-failure.png',fullPage:true});throw e}
finally{const report={completed:!failure,passed:Object.values(checks).filter(Boolean).length,checks,errors,failure};await writeFile('work/compact-paths-report.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));await browser.close()}
