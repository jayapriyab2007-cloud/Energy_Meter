import {useState,useEffect} from 'react'
import {LineChart,Line,BarChart,Bar,XAxis,YAxis,Tooltip,ResponsiveContainer,CartesianGrid} from 'recharts'
import CampusManagement from './pages/CampusManagement'
import MeterManagement from './pages/MeterManagement'
import DeviceManagement from './pages/DeviceManagement'

let TOKEN=localStorage.getItem('t')
const api=async(p,o={})=>{const r=await fetch('/api'+p,{...o,headers:{'Content-Type':'application/json',Authorization:'Bearer '+TOKEN},body:o.body&&JSON.stringify(o.body)});if(!r.ok)throw new Error((await r.json().catch(()=>({}))).detail||r.status);return r.json()}
function useGet(p,ms=3000){const[d,s]=useState(null);useEffect(()=>{if(!p)return;let on=1;const f=()=>api(p).then(x=>on&&s(x)).catch(()=>{});f();const i=setInterval(f,ms);return()=>{on=0;clearInterval(i)}},[p,ms]);return d}
const K=({l,v,w})=><div className={'card kpi'+(w?' warn':'')}><b>{v}</b><span>{l}</span></div>
const Chart=({data,x,y,bar})=><ResponsiveContainer width="100%" height={220}>{bar?<BarChart data={data}><CartesianGrid stroke="#e3eaef"/><XAxis dataKey={x}/><YAxis/><Tooltip/><Bar dataKey={y} fill="#0e7c86"/></BarChart>:<LineChart data={data}><CartesianGrid stroke="#e3eaef"/><XAxis dataKey={x} minTickGap={30}/><YAxis/><Tooltip/><Line dataKey={y} stroke="#0e7c86" dot={false} strokeWidth={2} isAnimationActive={false}/></LineChart>}</ResponsiveContainer>

function Overview(){const o=useGet('/overview');if(!o)return null
return<><h2>Campus overview</h2><p style={{color:'var(--mut)'}}>Data as of {String(o.as_of).replace('T',' ')} · {o.sim?'simulator running':'simulator stopped'}</p>
<div className="kpis"><K l="Current power (kW)" v={o.current_kw}/><K l="Today (kWh)" v={o.today_kwh}/><K l="Month so far (kWh)" v={o.month_kwh}/><K l="Estimated bill" v={'Rs '+o.est_bill.toLocaleString()}/><K l="Budget used" v={o.budget_pct+'%'} w={o.budget_pct>=90}/><K l="Open alerts" v={o.open_alerts} w={o.open_alerts>0}/><K l="Meters reporting" v={`${o.online}/${o.meters}`}/></div>
<div className="grid2"><div className="card"><b>Hourly use today (kWh)</b><Chart data={o.hourly} x="hour" y="kwh"/></div><div className="card"><b>Use by block today (kWh)</b><Chart data={o.blocks} x="block" y="kwh" bar/></div></div></>}

function Live({admin}){const rooms=useGet('/rooms',10000)||[];const[id,setId]=useState('');const rid=id||rooms[0]?.id;const l=useGet(rid?`/rooms/${rid}/live`:null);const rm=rooms.find(r=>r.id==rid)
return<><h2>Live monitoring</h2><div className="row" style={{marginBottom:12}}><select aria-label="Room" value={rid||''} onChange={e=>setId(e.target.value)}>{rooms.map(r=><option key={r.id} value={r.id}>{r.name} ({r.type})</option>)}</select>
{l&&<span className="tag">{l.online?'Receiving data':'No recent data'}</span>}{rm&&<span className="tag">{rm.source} data</span>}
{admin&&rid&&<button className="btn alt" onClick={()=>api('/sim/inject/anomaly',{method:'POST',body:{room_id:+rid,ticks:6}})}>Inject test anomaly</button>}</div>
<div className="card"><b>Power (kW), last 60 readings</b>{l&&<Chart data={l.points} x="t" y="kw"/>}</div></>}

function Alerts({admin}){const a=useGet('/alerts');const[n,setN]=useState({})
const act=(id,status)=>api('/alerts/'+id,{method:'PATCH',body:{status,note:n[id]||''}})
return<><h2>Alerts</h2>{a&&!a.length&&<div className="card">No alerts yet. Start the simulator, then inject a test anomaly from Live monitoring.</div>}
{a?.map(x=><div key={x.id} className={'card alert '+x.severity}><div className="row"><b>{x.room}</b><span>{x.kind}</span><span className={'tag '+x.severity}>{x.severity}</span><span className="tag">{x.status}</span><span style={{color:'var(--mut)'}}>{String(x.ts).replace('T',' ')}</span></div>
<p style={{margin:'6px 0'}}>{x.explanation}</p><p style={{margin:'0 0 8px',color:'var(--mut)'}}>Suggested action: {x.action}</p>
{admin&&x.status==='open'&&<div className="row"><input placeholder="Investigation note" onChange={e=>setN({...n,[x.id]:e.target.value})}/><button className="btn" onClick={()=>act(x.id,'resolved')}>Resolve</button><button className="btn alt" onClick={()=>act(x.id,'legitimate')}>Mark legitimate</button><button className="btn alt" onClick={()=>act(x.id,'false_positive')}>False positive</button></div>}
{x.note&&<small>Note: {x.note}</small>}</div>)}</>}

const D=['Mon','Tue','Wed','Thu','Fri','Sat','Sun'],H=[9,10,11,12,13,14,15,16],NX={Occupied:'Free',Free:'Break',Break:'Occupied'}
function Timetable({admin}){const rooms=useGet('/rooms',60000)||[];const[id,setId]=useState('');const rid=id||rooms[0]?.id;const[t,setT]=useState([])
const load=()=>rid&&api('/timetable/'+rid).then(setT);useEffect(()=>{load()},[rid])
const get=(d,h)=>t.find(x=>x.day===d&&x.hour===h)?.status||'Free'
const flip=async(d,h)=>{if(!admin)return;await api('/timetable/'+rid,{method:'PUT',body:{day:d,hour:h,status:NX[get(d,h)]}});load()}
return<><h2>Room timetable</h2><div className="row" style={{marginBottom:12}}><select aria-label="Room" value={rid||''} onChange={e=>setId(e.target.value)}>{rooms.map(r=><option key={r.id} value={r.id}>{r.name}</option>)}</select><span style={{color:'var(--mut)'}}>{admin?'Click a slot to switch between class, free and lunch. Anomaly checks use the change immediately.':'View only.'}</span></div>
<div className="card" style={{overflowX:'auto'}}><table className="tt"><thead><tr><th></th>{H.map(h=><th key={h}>{h}:00</th>)}</tr></thead><tbody>{D.map((d,i)=><tr key={d}><th>{d}</th>{H.map(h=>{const s=get(i,h);return<td key={h} className={s} onClick={()=>flip(i,h)}>{s==='Occupied'?'Class':s==='Free'?'Free':'Lunch'}</td>})}</tr>)}</tbody></table></div></>}

function Bills(){const f=useGet('/forecast',15000),o=useGet('/overview',15000);if(!f||!o)return null
return<><h2>Bills, budget and forecast</h2><div className="kpis"><K l="Bill so far (estimate)" v={'Rs '+o.est_bill.toLocaleString()}/><K l="Budget used" v={o.budget_pct+'%'} w={o.budget_pct>=90}/><K l="Forecast month (kWh)" v={f.month_kwh}/><K l="Forecast month cost" v={'Rs '+f.month_cost.toLocaleString()}/></div>
<div className="card"><b>Daily use, last full days (kWh)</b><Chart data={f.daily} x="day" y="kwh" bar/><small style={{color:'var(--mut)'}}>{f.method}. Tariff Rs {o.tariff}/kWh.</small></div></>}

function Assistant(){const[m,setM]=useState([{a:'Ask about your bill, highest block or room, alerts, or current demand.'}]);const[q,setQ]=useState('')
const send=async e=>{e.preventDefault();if(!q)return;const x=q;setQ('');setM(m=>[...m,{u:x}]);const r=await api('/assistant',{method:'POST',body:{q:x}});setM(m=>[...m,{a:r.a}])}
return<><h2>Energy assistant</h2><div className="card"><div className="chat">{m.map((x,i)=><div key={i} className={x.u?'u':'a'}>{x.u||x.a}</div>)}</div><form className="row" onSubmit={send}><input style={{flex:1}} value={q} onChange={e=>setQ(e.target.value)} placeholder="Why did I get an alert?"/><button className="btn">Ask</button></form></div></>}

function Login({done}){const[u,setU]=useState('admin'),[p,setP]=useState('admin123'),[e,setE]=useState('')
const go=async ev=>{ev.preventDefault();try{const r=await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:u,password:p})});const j=await r.json();if(!r.ok)throw new Error(j.detail);TOKEN=j.token;localStorage.setItem('t',j.token);localStorage.setItem('r',j.role);done(j.role)}catch(x){setE(x.message)}}
return<form className="card login" onSubmit={go}><h2>Campus Energy</h2><input aria-label="Username" value={u} onChange={e=>setU(e.target.value)}/><input aria-label="Password" type="password" value={p} onChange={e=>setP(e.target.value)}/>{e&&<p style={{color:'var(--red)'}}>{e}</p>}<button className="btn">Sign in</button><p style={{color:'var(--mut)',fontSize:13}}>Demo: admin / admin123, consumer / consumer123</p></form>}

export default function App(){const[role,setRole]=useState(TOKEN&&localStorage.getItem('r'));const[tab,setTab]=useState('Overview');const[sim,setSim]=useState(false)
if(!role)return<Login done={setRole}/>
const admin=role==='admin'
const tabs={
  Overview,
  'Live monitoring':Live,
  Alerts,
  Timetable,
  'Campus':CampusManagement,
  'Meters':MeterManagement,
  'IoT Devices':DeviceManagement,
  'Bills & forecast':Bills,
  Assistant
};
const T=tabs[tab]
return<div className="app"><nav><h1>Campus Energy<small>{admin?'Administrator':'Consumer'} view</small></h1>{Object.keys(tabs).map(k=><button key={k} className={k===tab?'on':''} onClick={()=>setTab(k)}>{k}</button>)}
{admin&&<button onClick={async()=>setSim(await api('/sim/'+(sim?'stop':'start'),{method:'POST'}))}>{sim?'Stop simulator':'Start simulator'}</button>}
<button onClick={()=>{localStorage.clear();TOKEN=null;setRole(null)}} style={{marginTop:'auto'}}>Sign out</button></nav><main><T admin={admin}/></main></div>}
