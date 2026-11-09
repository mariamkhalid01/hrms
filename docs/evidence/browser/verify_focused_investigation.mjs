import {createRequire} from 'node:module';
import {writeFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
const require=createRequire('C:/Program Files/WindowsApps/OpenAI.CodexPrimaryRuntime.v26-1104-2876-0_26.1104.2876.0_x64__3k8sg7r9htsxt/dependencies/node/node_modules/');
const {chromium}=require('playwright');
const browser=await chromium.launch({channel:'msedge',headless:true});
const page=await browser.newPage({viewport:{width:1440,height:1000}});
page.setDefaultTimeout(20000);
const dataset='cbd64c13-9b05-42e0-86d2-c0cd2fba1a12';
const checks={},errors=[];let failure;
const check=(name,ok)=>{checks[name]=!!ok;assert(ok,name)};
page.on('pageerror',e=>errors.push(e.message));
const go=async route=>{await page.goto(`http://127.0.0.1:5173/${route}?dataset=${dataset}`)};
const api=async path=>{const r=await page.request.get(`http://127.0.0.1:5173/api/v1/datasets/${dataset}${path}`);assert(r.ok());return r.json()};
try{
 for(const width of [1440,1100,961,768,390,320]){
  await page.setViewportSize({width,height:1000});
  for(const [route,selector] of [['bottlenecks','.finding-summary'],['recommendations','.recommendation-card']]){
   await go(route);await page.locator(selector).first().waitFor();
   check(`${route}_${width}_fits`,await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
   check(`${route}_${width}_six_rows`,await page.locator(selector).count()===6);
   if(width===1440){
    const height=await page.locator(selector).first().evaluate(el=>el.getBoundingClientRect().height);
    check(`${route}_compact_rows`,height<150);
    await page.screenshot({path:`work/focused-${route}-desktop.png`,fullPage:true});
   }
   if(width===390)await page.screenshot({path:`work/focused-${route}-mobile.png`,fullPage:true});
  }
 }
 await page.setViewportSize({width:1440,height:1000});
 await go('bottlenecks');await page.locator('.finding-summary').first().waitFor();
 const unfiltered=await api('/analytics/findings?limit=6');
 check('finding_entities_match_api',JSON.stringify(await page.locator('.finding-summary-main h3').allTextContents())===JSON.stringify(unfiltered.items.map(f=>f.entity.label)));
 check('observed_and_threshold_visible',await page.locator('.finding-summary-measure small').count()===6);
 await page.getByRole('button',{name:'More filters',exact:true}).click();await page.getByLabel('Severity',{exact:true}).selectOption('high');
 await page.getByLabel('Bottleneck category',{exact:true}).selectOption('long_waiting');
 await page.waitForFunction(()=>document.querySelectorAll('.finding-summary').length>0&&!document.body.textContent.includes('Loading findings…'));
 const filtered=await api('/analytics/findings?limit=6&severity=high&category=long_waiting');
 check('finding_filters_use_actual_data',JSON.stringify(await page.locator('.finding-summary-main h3').allTextContents())===JSON.stringify(filtered.items.map(f=>f.entity.label)));
 await page.getByRole('button',{name:/Understand finding:/}).first().click();await page.getByRole('dialog').waitFor();
 check('finding_evidence_popup',await page.getByRole('heading',{name:'What was observed',exact:true}).isVisible());
 check('comparison_threshold_preserved',await page.getByText('Review threshold',{exact:true}).isVisible());
 await page.keyboard.press('Escape');await page.getByRole('dialog').waitFor({state:'hidden'});
 await go('recommendations');await page.locator('.recommendation-card').first().waitFor();
 const recs=await api('/recommendations?limit=6');
 check('recommendation_targets_match_api',JSON.stringify(await page.locator('.recommendation-target').allTextContents())===JSON.stringify(recs.items.map(r=>r.entity.label)));
 await page.locator('.recommendation-card').first().click();await page.getByRole('dialog').waitFor();
 check('recommendation_plan_popup',await page.getByRole('heading',{name:'A practical review plan',exact:true}).isVisible());
 check('recommendation_real_actions',await page.locator('.recommendation-action-steps li').count()===recs.items[0].actions.length);
 await page.keyboard.press('Escape');
 await page.setViewportSize({width:390,height:844});await page.locator('.recommendation-card').first().click();await page.getByRole('dialog').waitFor();
 check('mobile_popup_fits',await page.getByRole('dialog').evaluate(el=>el.scrollWidth<=el.clientWidth&&el.getBoundingClientRect().right<=innerWidth));
 await page.keyboard.press('Escape');
 check('no_browser_errors',errors.length===0);
}catch(e){failure=String(e);await page.screenshot({path:'work/focused-investigation-failure.png',fullPage:true});throw e}
finally{const report={passed:Object.values(checks).filter(Boolean).length,checks,errors,failure};await writeFile('work/focused-investigation-report.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));await browser.close()}
