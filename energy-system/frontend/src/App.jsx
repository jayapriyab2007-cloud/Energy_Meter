import {useState,useEffect} from 'react'
import {LineChart,Line,BarChart,Bar,XAxis,YAxis,Tooltip,ResponsiveContainer,CartesianGrid} from 'recharts'
import CampusManagement from './pages/CampusManagement'

let TOKEN=localStorage.getItem('t')
const api=async(p,o={})=>{const r=await fetch('/api'+p,{...o,headers:{'Content-Type':'application/json',Authorization:'Bearer '+TOKEN},body:o.body&&JSON.stringify(o.body)});if(!r.ok)throw new Error((await r.json().catch(()=>({}))).detail||r.status);return r.json()}
function useGet(p,ms=3000){const[d,s]=useState(null);useEffect(()=>{if(!p)return;let on=1;const f=()=>api(p).then(x=>on&&s(x)).catch(()=>{});f();const i=setInterval(f,ms);return()=>{on=0;clearInterval(i)}},[p,ms]);return d}
const K=({l,v,w})=><div className={'card kpi'+(w?' warn':'')}><b>{v}</b><span>{l}</span></div>
const Chart=({data,x,y,bar})=><ResponsiveContainer width="100%" height={220}>{bar?<BarChart data={data}><CartesianGrid stroke="#e3eaef"/><XAxis dataKey={x}/><YAxis/><Tooltip/><Bar dataKey={y} fill="#0e7c86"/></BarChart>:<LineChart data={data}><CartesianGrid stroke="#e3eaef"/><XAxis dataKey={x} minTickGap={30}/><YAxis/><Tooltip/><Line dataKey={y} stroke="#0e7c86" dot={false} strokeWidth={2} isAnimationActive={false}/></LineChart>}</ResponsiveContainer>

function Overview(){const o=useGet('/overview');if(!o)return null
return<>
<div className="row" style={{marginBottom:10,justifyContent:'space-between'}}>
  <h2>Campus overview</h2>
  <span className="tag" style={{background:'#e0f2f1',color:'#004d40',border:'1px solid #b2dfdb',fontSize:13}}>
    College Demo Mode · Simulated Data (Cost Estimate Only)
  </span>
</div>
<p style={{color:'var(--mut)'}}>Data as of {String(o.as_of).replace('T',' ')} · {o.sim?'simulator running':'simulator stopped'}</p>
<div className="kpis">
  <K l="Current power (kW)" v={o.current_kw}/>
  <K l="Today (kWh)" v={o.today_kwh}/>
  <K l="Month so far (kWh)" v={o.month_kwh}/>
  <K l="Estimated bill" v={'Rs '+o.est_bill.toLocaleString()}/>
  <K l="Budget used" v={o.budget_pct+'%'} w={o.budget_pct>=90}/>
  <K l="Open alerts" v={o.open_alerts} w={o.open_alerts>0}/>
  <K l="Meters reporting" v={`${o.online}/${o.meters}`}/>
</div>
<div className="grid2" style={{marginBottom:12}}>
  <div className="card"><b>Hourly use today (kWh)</b><Chart data={o.hourly} x="hour" y="kwh"/></div>
  <div className="card"><b>Use by block today (kWh)</b><Chart data={o.blocks} x="block" y="kwh" bar/></div>
</div>
{o.departments && (
  <div className="card">
    <b>Use by department today (kWh)</b>
    <Chart data={o.departments.slice(0, 8)} x="department" y="kwh" bar/>
  </div>
)}
</>}

function RoomSelector({rooms,value,onChange}){
  const blocks=['A','B','C','D']
  return (
    <select aria-label="Room" value={value||''} onChange={e=>onChange(e.target.value)}>
      {blocks.map(b=>{
        const bRooms=rooms.filter(r=>r.block===b)
        if(!bRooms.length)return null
        return (
          <optgroup key={b} label={`Block ${b}`}>
            {bRooms.map(r=>(
              <option key={r.id} value={r.id}>
                {r.name} - Floor {r.floor} ({r.type}) [{r.department}]
              </option>
            ))}
          </optgroup>
        )
      })}
    </select>
  )
}

function Live({admin}){
  const rooms=useGet('/rooms',10000)||[];const[id,setId]=useState('');const rid=id||rooms[0]?.id;const l=useGet(rid?`/rooms/${rid}/live`:null);const rm=rooms.find(r=>r.id==rid)
  return<>
  <h2>Live monitoring</h2>
  <div className="row" style={{marginBottom:12}}>
    <RoomSelector rooms={rooms} value={rid} onChange={setId}/>
    {l&&<span className="tag">{l.online?'Receiving data':'No recent data'}</span>}
    {rm&&<span className="tag">{rm.type}</span>}
    {rm&&<span className="tag Medium">{rm.department}</span>}
    <span className="tag alt">Simulated telemetry</span>
    {admin&&rid&&<button className="btn alt" onClick={()=>api('/sim/inject/anomaly',{method:'POST',body:{room_id:+rid,ticks:6}})}>Inject test load</button>}
  </div>
  <div className="card">
    <b>Power (kW), last 60 readings {rm&&`· ${rm.name} (${rm.type})`}</b>
    {l&&<Chart data={l.points} x="t" y="kw"/>}
  </div>
  </>
}

function Alerts({admin}){
  const a=useGet('/alerts');const[n,setN]=useState({})
  const[excModal,setExcModal]=useState(null) // alert object
  const[excActivity,setExcActivity]=useState('')
  const[excReason,setExcReason]=useState('')

  const act=(id,status)=>api('/alerts/'+id,{method:'PATCH',body:{status,note:n[id]||''}})

  const submitException=async e=>{
    e.preventDefault()
    if(!excModal||!excActivity)return
    const start=new Date(excModal.ts)
    start.setMinutes(start.getMinutes()-15)
    const end=new Date(excModal.ts)
    end.setHours(end.getHours()+2)

    await api('/demo/exception',{
      method:'POST',
      body:{
        room_id:excModal.room_id,
        start_ts:start.toISOString(),
        end_ts:end.toISOString(),
        activity:excActivity,
        reason:excReason||'Legitimate unrecorded activity',
        alert_id:excModal.id
      }
    })
    setExcModal(null)
    setExcActivity('')
    setExcReason('')
  }

  return<>
  <h2>Alerts & investigations</h2>
  <p style={{color:'var(--mut)',marginBottom:16}}>
    Timetable-aware anomaly alerts. Wording emphasizes investigation rather than assuming waste.
  </p>

  {excModal && (
    <div className="card" style={{marginBottom:16,borderColor:'var(--teal)',background:'#f0fdfa'}}>
      <b>Add timetable exception for {excModal.room}</b>
      <p style={{fontSize:13,margin:'6px 0 10px'}}>
        Creates an authorized schedule override for this time slot, marking the alert legitimate and preventing future false anomalies.
      </p>
      <form onSubmit={submitException} className="row" style={{gap:10}}>
        <input
          placeholder="Activity name (e.g. Setup for 12:00 seminar)"
          style={{flex:1}}
          value={excActivity}
          onChange={e=>setExcActivity(e.target.value)}
          required
        />
        <input
          placeholder="Reason / Notes"
          style={{flex:1}}
          value={excReason}
          onChange={e=>setExcReason(e.target.value)}
        />
        <button className="btn" type="submit">Save exception</button>
        <button className="btn alt" type="button" onClick={()=>setExcModal(null)}>Cancel</button>
      </form>
    </div>
  )}

  {a&&!a.length&&<div className="card">No open alerts. Head to Demo control to trigger a scenario.</div>}
  {a?.map(x=><div key={x.id} className={'card alert '+x.severity}>
    <div className="row" style={{marginBottom:4}}>
      <b>{x.room}</b>
      <span className="tag">Block {x.block}, Floor {x.floor}</span>
      <span className="tag Medium">{x.department}</span>
      <span>{x.kind}</span>
      <span className={'tag '+x.severity}>{x.severity}</span>
      <span className="tag">{x.status}</span>
      <span style={{color:'var(--mut)'}}>{String(x.ts).replace('T',' ')}</span>
    </div>
    <p style={{margin:'6px 0'}}>{x.explanation}</p>
    <p style={{margin:'0 0 8px',color:'var(--mut)'}}>Suggested action: {x.action}</p>
    {admin&&x.status==='open'&&(
      <div className="row">
        <input placeholder="Investigation note" onChange={e=>setN({...n,[x.id]:e.target.value})}/>
        <button className="btn" onClick={()=>act(x.id,'resolved')}>Resolve</button>
        <button className="btn alt" onClick={()=>act(x.id,'legitimate')}>Mark legitimate</button>
        <button className="btn alt" onClick={()=>setExcModal(x)}>Add exception</button>
        <button className="btn alt" onClick={()=>act(x.id,'false_positive')}>False positive</button>
      </div>
    )}
    {x.note&&<small style={{display:'block',marginTop:6}}>Note: {x.note}</small>}
  </div>)}
  </>
}

const D=['Mon','Tue','Wed','Thu','Fri','Sat','Sun'],H=[9,10,11,12,13,14,15,16],NX={Occupied:'Free',Free:'Break',Break:'Occupied'}
function Timetable({admin}){
  const rooms=useGet('/rooms',60000)||[];const[id,setId]=useState('');const rid=id||rooms.find(r=>r.name==='B101')?.id||rooms[0]?.id;const[t,setT]=useState([])
  const load=()=>rid&&api('/timetable/'+rid).then(setT);useEffect(()=>{load()},[rid])
  const getSlot=(d,h)=>t.find(x=>x.day===d&&x.hour===h)||{status:'Free',activity:'Free period'}
  const flip=async(d,h)=>{if(!admin)return;const curr=getSlot(d,h).status;await api('/timetable/'+rid,{method:'PUT',body:{day:d,hour:h,status:NX[curr]}});load()}
  const rm=rooms.find(r=>r.id==rid)

  return<>
  <h2>Room timetable schedule</h2>
  <div className="row" style={{marginBottom:12}}>
    <RoomSelector rooms={rooms} value={rid} onChange={setId}/>
    {rm&&<span className="tag">{rm.type}</span>}
    {rm&&<span className="tag Medium">{rm.department}</span>}
    <span style={{color:'var(--mut)'}}>{admin?'Click a slot to toggle between Class, Free, and Lunch.':'View only.'}</span>
  </div>
  <div className="card" style={{overflowX:'auto'}}>
    <table className="tt" style={{width:'100%'}}>
      <thead><tr><th>Day</th>{H.map(h=><th key={h}>{h}:00 - {h+1}:00</th>)}</tr></thead>
      <tbody>
        {D.map((d,i)=><tr key={d}>
          <th>{d}</th>
          {H.map(h=>{
            const s=getSlot(i,h)
            return (
              <td key={h} className={s.status} onClick={()=>flip(i,h)} title={s.activity}>
                <b>{s.status==='Occupied'?'Class':s.status==='Free'?'Free':'Lunch'}</b>
                <div style={{fontSize:11,color:'var(--mut)',marginTop:2,lineHeight:1.1}}>{s.activity}</div>
              </td>
            )
          })}
        </tr>)}
      </tbody>
    </table>
  </div>
  </>
}

function Assistant(){
  const[m,setM]=useState([{a:'Hello! Ask about campus electricity usage, highest consuming blocks/departments, alerts for the B101 seminar hall, or current power demand.'}]);const[q,setQ]=useState('')
  const send=async e=>{e.preventDefault();if(!q)return;const x=q;setQ('');setM(m=>[...m,{u:x}]);const r=await api('/assistant',{method:'POST',body:{q:x}});setM(m=>[...m,{a:r.a}])}
  return<>
  <h2>College energy assistant</h2>
  <div className="card">
    <div className="chat">{m.map((x,i)=><div key={i} className={x.u?'u':'a'}>{x.u||x.a}</div>)}</div>
    <form className="row" onSubmit={send}>
      <input style={{flex:1}} value={q} onChange={e=>setQ(e.target.value)} placeholder="e.g. Which block uses the most power? or Why was an alert raised for the seminar hall?"/>
      <button className="btn">Ask</button>
    </form>
  </div>
  </>
}

function Login({done}){
  const[u,setU]=useState('admin'),[p,setP]=useState('admin123'),[e,setE]=useState('')
  const go=async ev=>{ev.preventDefault();try{const r=await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:u,password:p})});const j=await r.json();if(!r.ok)throw new Error(j.detail);TOKEN=j.token;localStorage.setItem('t',j.token);localStorage.setItem('r',j.role);done(j.role)}catch(x){setE(x.message)}}
  return (
    <form className="card login" onSubmit={go}>
      <h2>Campus Energy</h2>
      <p style={{fontSize:13,color:'var(--mut)',margin:'0 0 14px'}}>College Smart Energy Intelligence & Monitoring</p>
      <input aria-label="Username" value={u} onChange={e=>setU(e.target.value)}/>
      <input aria-label="Password" type="password" value={p} onChange={e=>setP(e.target.value)}/>
      {e&&<p style={{color:'var(--red)'}}>{e}</p>}
      <button className="btn">Sign in</button>
      <p style={{color:'var(--mut)',fontSize:13,marginTop:12}}>Demo credentials: admin / admin123, consumer / consumer123</p>
    </form>
  )
}

export default function App(){
  const[role,setRole]=useState(TOKEN&&localStorage.getItem('r'));const[tab,setTab]=useState('Overview');const[sim,setSim]=useState(false)
  if(!role)return<Login done={setRole}/>
  const admin=role==='admin'
  const tabs={
    Overview,
    'Live monitoring':Live,
    Alerts,
    Timetable,
    'Campus':CampusManagement,
    Assistant
  };
  const T=tabs[tab]
  return (
    <div className="app">
      <nav>
        <h1>College Energy<small>{admin?'Administrator':'Consumer'} view</small></h1>
        {Object.keys(tabs).map(k=><button key={k} className={k===tab?'on':''} onClick={()=>setTab(k)}>{k}</button>)}
        {admin&&<button onClick={async()=>setSim(await api('/sim/'+(sim?'stop':'start'),{method:'POST'}))}>{sim?'Stop simulator':'Start simulator'}</button>}
        <button onClick={()=>{localStorage.clear();TOKEN=null;setRole(null)}} style={{marginTop:'auto'}}>Sign out</button>
      </nav>
      <main><T admin={admin}/></main>
    </div>
  )
}
