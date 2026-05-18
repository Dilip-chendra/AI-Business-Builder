"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { Loader2, Check, Star, ChevronDown, ChevronUp, ArrowRight, Zap, Shield, BarChart2, Users, Clock, Globe, Lock, Sparkles } from "lucide-react";
import { api } from "@/lib/api";
import type { Business, Product } from "@/lib/types";

const SCHEMES: Record<string,{primary:string;light:string;glow:string;dark:string}> = {
  indigo:  {primary:"#6366f1",light:"#ede9fe",glow:"rgba(99,102,241,0.35)",dark:"#4f46e5"},
  emerald: {primary:"#10b981",light:"#d1fae5",glow:"rgba(16,185,129,0.35)",dark:"#059669"},
  rose:    {primary:"#f43f5e",light:"#ffe4e6",glow:"rgba(244,63,94,0.35)",dark:"#e11d48"},
  amber:   {primary:"#f59e0b",light:"#fef3c7",glow:"rgba(245,158,11,0.35)",dark:"#d97706"},
  sky:     {primary:"#0ea5e9",light:"#e0f2fe",glow:"rgba(14,165,233,0.35)",dark:"#0284c7"},
  violet:  {primary:"#8b5cf6",light:"#ede9fe",glow:"rgba(139,92,246,0.35)",dark:"#7c3aed"},
};
const ICON_MAP: Record<string,any> = {zap:Zap,shield:Shield,chart:BarChart2,users:Users,star:Star,clock:Clock,globe:Globe,lock:Lock};
function Stars({n}:{n:number}){
  return(<div style={{display:"flex",gap:2}}>{Array.from({length:5}).map((_,i)=>(<Star key={i} size={14} fill={i<n?"#f59e0b":"none"} stroke={i<n?"#f59e0b":"#d1d5db"}/>))}</div>);
}
export default function LandingPage() {
  const params = useParams();
  const id = params?.id as string;
  const [biz, setBiz] = useState<Business | null>(null);
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [missing, setMissing] = useState(false);
  const [openFaq, setOpenFaq] = useState<number | null>(null);

  useEffect(() => {
    if (!id) return;
    const previewMode = typeof window !== "undefined" && window.location.search.includes("preview=1");
    // Use public endpoints — landing page is visible without auth
    const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
    Promise.all([
      fetch(`${API_URL}/businesses/${id}/${previewMode ? "landing-page-preview" : "landing-page"}`).then(r => r.ok ? r.json() : Promise.reject()),
      fetch(`${API_URL}/businesses/${id}/products-public`).then(r => r.ok ? r.json() : []).catch(() => []),
    ])
      .then(([b, p]) => {
        setBiz(b);
        setProducts(p as Product[]);
        // Track visit (fire and forget — no auth needed for tracking)
        fetch(`${API_URL}/analytics/track`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ business_id: id, event_type: "visit", source: "landing" }),
        }).catch(() => {});
      })
      .catch(() => setMissing(true))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return (
    <div style={{minHeight:"100vh",display:"flex",alignItems:"center",justifyContent:"center",background:"#f8fafc"}}>
      <div style={{textAlign:"center"}}>
        <Loader2 size={40} className="animate-spin" style={{color:"#6366f1",margin:"0 auto 12px"}}/>
        <p style={{color:"#64748b",fontSize:15}}>Building your landing page…</p>
      </div>
    </div>
  );

  if (missing || !biz) return (
    <div style={{minHeight:"100vh",display:"flex",alignItems:"center",justifyContent:"center",background:"#f8fafc"}}>
      <div style={{textAlign:"center",padding:"0 24px"}}>
        <h1 style={{fontSize:24,fontWeight:800,color:"#0f172a",marginBottom:8}}>Business not found</h1>
        <Link href="/dashboard" style={{color:"#6366f1",fontWeight:600,textDecoration:"none"}}>← Back to Dashboard</Link>
      </div>
    </div>
  );

  const pc = biz.page_content || {};
  const scheme = SCHEMES[(pc.color_scheme as string) || "indigo"] || SCHEMES.indigo;
  const painPoints: string[] = (pc.pain_points as string[]) || [];
  const benefits: string[] = (pc.benefits as string[]) || [];
  const features: any[] = (pc.features as any[]) || [];
  const socialProof: any[] = (pc.social_proof as any[]) || [];
  const faq: any[] = (pc.faq as any[]) || [];
  const pricingTiers: any[] = (pc.pricing_tiers as any[]) || [];
  const trustBadges: string[] = (pc.trust_badges as string[]) || [];
  const urgencyText: string = (pc.urgency_text as string) || "";
  return (
    <div style={{minHeight:"100vh",background:"#f8fafc",fontFamily:"-apple-system,BlinkMacSystemFont,Inter,sans-serif"}}>

      {/* NAV */}
      <nav style={{position:"sticky",top:0,zIndex:50,background:"rgba(255,255,255,0.97)",backdropFilter:"blur(8px)",borderBottom:"1px solid #e2e8f0"}}>
        <div style={{maxWidth:1100,margin:"0 auto",padding:"14px 24px",display:"flex",alignItems:"center",justifyContent:"space-between"}}>
          <span style={{fontWeight:900,fontSize:18,color:"#0f172a"}}>{biz.name}</span>
          <div style={{display:"flex",gap:10,alignItems:"center"}}>
            {pricingTiers.length>0&&<a href="#pricing" style={{fontSize:13,fontWeight:600,color:"#64748b",textDecoration:"none"}}>Pricing</a>}
            <a href="#cta" style={{fontSize:13,fontWeight:700,color:"#fff",background:scheme.primary,padding:"8px 18px",borderRadius:10,textDecoration:"none",boxShadow:`0 4px 14px ${scheme.glow}`}}>{biz.cta_text}</a>
          </div>
        </div>
      </nav>

      {/* HERO */}
      <section style={{background:"linear-gradient(135deg,#0f172a 0%,#1a1040 60%,#0f172a 100%)",padding:"90px 24px 110px",position:"relative",overflow:"hidden"}}>
        <div style={{position:"absolute",top:-80,right:-80,width:400,height:400,borderRadius:"50%",background:`${scheme.primary}22`,filter:"blur(80px)"}}/>
        <div style={{position:"absolute",bottom:-60,left:60,width:300,height:300,borderRadius:"50%",background:`${scheme.primary}15`,filter:"blur(60px)"}}/>
        <div style={{maxWidth:780,margin:"0 auto",textAlign:"center",position:"relative"}}>
          <div style={{display:"inline-flex",alignItems:"center",gap:6,background:`${scheme.primary}25`,color:scheme.primary,borderRadius:99,padding:"6px 16px",fontSize:12,fontWeight:700,marginBottom:20,border:`1px solid ${scheme.primary}40`}}>
            <Sparkles size={12}/> {biz.niche}
          </div>
          <h1 style={{fontSize:"clamp(34px,5.5vw,62px)",fontWeight:900,color:"#fff",margin:"0 0 20px",lineHeight:1.1,letterSpacing:"-0.02em"}}>{biz.headline}</h1>
          <p style={{fontSize:"clamp(16px,2vw,20px)",color:"rgba(255,255,255,0.65)",margin:"0 0 16px",lineHeight:1.7,maxWidth:620,marginLeft:"auto",marginRight:"auto"}}>{biz.subheading}</p>
          {urgencyText&&<p style={{fontSize:13,color:"#fbbf24",fontWeight:600,margin:"0 0 32px"}}>⚡ {urgencyText}</p>}
          <div style={{display:"flex",gap:12,justifyContent:"center",flexWrap:"wrap"}}>
            <a id="cta" href={pricingTiers.length>0?"#pricing":"#about"} style={{display:"inline-flex",alignItems:"center",gap:8,background:`linear-gradient(135deg,${scheme.primary},${scheme.dark})`,color:"#fff",fontWeight:800,fontSize:16,padding:"15px 32px",borderRadius:14,textDecoration:"none",boxShadow:`0 8px 30px ${scheme.glow}`}}>
              {biz.cta_text} <ArrowRight size={18}/>
            </a>
          </div>
          {trustBadges.length>0&&(
            <div style={{display:"flex",gap:20,justifyContent:"center",flexWrap:"wrap",marginTop:20}}>
              {trustBadges.map((b:string)=>(<span key={b} style={{display:"flex",alignItems:"center",gap:5,fontSize:12,color:"rgba(255,255,255,0.5)"}}><Check size={12} style={{color:scheme.primary}}/> {b}</span>))}
            </div>
          )}
        </div>
      </section>
      {/* PAIN POINTS */}
      {painPoints.length>0&&(
        <section style={{background:"#fff",padding:"64px 24px"}}>
          <div style={{maxWidth:900,margin:"0 auto"}}>
            <p style={{textAlign:"center",fontSize:11,fontWeight:700,letterSpacing:"0.1em",textTransform:"uppercase",color:"#94a3b8",marginBottom:12}}>Sound familiar?</p>
            <h2 style={{textAlign:"center",fontSize:"clamp(24px,3vw,36px)",fontWeight:800,color:"#0f172a",margin:"0 0 40px"}}>You&apos;re not alone in this struggle</h2>
            <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(260px,1fr))",gap:16}}>
              {painPoints.map((pain:string,i:number)=>(
                <div key={i} style={{background:"#fef2f2",borderRadius:16,border:"1px solid #fecaca",padding:"20px 22px",display:"flex",gap:12}}>
                  <span style={{fontSize:20,flexShrink:0}}>😤</span>
                  <p style={{fontSize:14,color:"#7f1d1d",lineHeight:1.6,margin:0,fontWeight:500}}>{pain}</p>
                </div>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* BENEFITS */}
      {benefits.length>0&&(
        <section style={{background:scheme.light,padding:"64px 24px"}}>
          <div style={{maxWidth:900,margin:"0 auto"}}>
            <p style={{textAlign:"center",fontSize:11,fontWeight:700,letterSpacing:"0.1em",textTransform:"uppercase",color:scheme.primary,marginBottom:12}}>The transformation</p>
            <h2 style={{textAlign:"center",fontSize:"clamp(24px,3vw,36px)",fontWeight:800,color:"#0f172a",margin:"0 0 40px"}}>Here&apos;s what changes when you use {biz.name}</h2>
            <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(260px,1fr))",gap:16}}>
              {benefits.map((benefit:string,i:number)=>(
                <div key={i} style={{background:"#fff",borderRadius:16,border:`1px solid ${scheme.primary}30`,padding:"22px 24px",display:"flex",gap:12}}>
                  <div style={{width:28,height:28,borderRadius:"50%",background:`linear-gradient(135deg,${scheme.primary},${scheme.dark})`,display:"flex",alignItems:"center",justifyContent:"center",flexShrink:0}}>
                    <Check size={14} color="#fff"/>
                  </div>
                  <p style={{fontSize:14,color:"#1e293b",lineHeight:1.6,margin:0,fontWeight:600}}>{benefit}</p>
                </div>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* FEATURES */}
      {features.length>0&&(
        <section id="about" style={{background:"#fff",padding:"80px 24px"}}>
          <div style={{maxWidth:1100,margin:"0 auto"}}>
            <p style={{textAlign:"center",fontSize:11,fontWeight:700,letterSpacing:"0.1em",textTransform:"uppercase",color:"#94a3b8",marginBottom:12}}>Features</p>
            <h2 style={{textAlign:"center",fontSize:"clamp(24px,3vw,36px)",fontWeight:800,color:"#0f172a",margin:"0 0 8px"}}>Everything you need, nothing you don&apos;t</h2>
            <p style={{textAlign:"center",fontSize:16,color:"#64748b",margin:"0 0 48px"}}>{biz.product_pitch}</p>
            <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(240px,1fr))",gap:20}}>
              {features.map((f:any,i:number)=>{
                const Icon=ICON_MAP[f.icon_hint]||Zap;
                return(
                  <div key={i} style={{background:"#f8fafc",borderRadius:18,border:"1px solid #e2e8f0",padding:"24px 22px"}}>
                    <div style={{width:44,height:44,borderRadius:12,background:`linear-gradient(135deg,${scheme.primary},${scheme.dark})`,display:"flex",alignItems:"center",justifyContent:"center",marginBottom:14,boxShadow:`0 4px 14px ${scheme.glow}`}}>
                      <Icon size={20} color="#fff"/>
                    </div>
                    <h3 style={{fontSize:16,fontWeight:800,color:"#0f172a",margin:"0 0 8px"}}>{f.title}</h3>
                    <p style={{fontSize:14,color:"#64748b",lineHeight:1.6,margin:0}}>{f.description}</p>
                  </div>
                );
              })}
            </div>
          </div>
        </section>
      )}
      {/* SOCIAL PROOF */}
      {socialProof.length>0&&(
        <section style={{background:"#0f172a",padding:"80px 24px"}}>
          <div style={{maxWidth:1100,margin:"0 auto"}}>
            <p style={{textAlign:"center",fontSize:11,fontWeight:700,letterSpacing:"0.1em",textTransform:"uppercase",color:scheme.primary,marginBottom:12}}>Real results</p>
            <h2 style={{textAlign:"center",fontSize:"clamp(24px,3vw,36px)",fontWeight:800,color:"#fff",margin:"0 0 48px"}}>Trusted by {biz.target_audience}</h2>
            <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(300px,1fr))",gap:20}}>
              {socialProof.map((t:any,i:number)=>(
                <div key={i} style={{background:"rgba(255,255,255,0.05)",borderRadius:18,border:"1px solid rgba(255,255,255,0.1)",padding:"26px 24px"}}>
                  <Stars n={t.rating||5}/>
                  <p style={{fontSize:15,color:"rgba(255,255,255,0.85)",lineHeight:1.7,margin:"14px 0 18px",fontStyle:"italic"}}>&ldquo;{t.quote}&rdquo;</p>
                  <div>
                    <p style={{fontWeight:700,fontSize:14,color:"#fff",margin:0}}>{t.name}</p>
                    <p style={{fontSize:12,color:"rgba(255,255,255,0.45)",margin:"2px 0 0"}}>{t.role}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>
      )}
      {/* PRODUCTS — show real products from DB if no pricing tiers */}
      {products.length > 0 && pricingTiers.length === 0 && (
        <section id="pricing" style={{background:"#f8fafc",padding:"80px 24px"}}>
          <div style={{maxWidth:1100,margin:"0 auto"}}>
            <p style={{textAlign:"center",fontSize:11,fontWeight:700,letterSpacing:"0.1em",textTransform:"uppercase",color:"#94a3b8",marginBottom:12}}>Products</p>
            <h2 style={{textAlign:"center",fontSize:"clamp(24px,3vw,36px)",fontWeight:800,color:"#0f172a",margin:"0 0 8px"}}>What you get</h2>
            <p style={{textAlign:"center",fontSize:16,color:"#64748b",margin:"0 0 48px"}}>Everything you need to get started.</p>
            <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(280px,1fr))",gap:20,alignItems:"start"}}>
              {products.map((prod: any, i: number) => (
                <div key={prod.id} style={{background:"#fff",borderRadius:20,border:`1px solid #e2e8f0`,padding:"32px 28px",boxShadow:"0 2px 12px rgba(0,0,0,0.04)"}}>
                  <p style={{fontSize:13,fontWeight:700,color:"#94a3b8",margin:"0 0 8px",textTransform:"uppercase",letterSpacing:"0.06em"}}>{prod.category}</p>
                  <h3 style={{fontSize:20,fontWeight:900,color:"#0f172a",margin:"0 0 10px"}}>{prod.name}</h3>
                  <p style={{fontSize:14,color:"#64748b",lineHeight:1.6,margin:"0 0 20px"}}>{prod.description}</p>
                  <div style={{display:"flex",alignItems:"baseline",gap:4,marginBottom:24}}>
                    <span style={{fontSize:38,fontWeight:900,color:"#0f172a"}}>${Number(prod.price).toFixed(2)}</span>
                    <span style={{fontSize:14,color:"#94a3b8"}}>{prod.currency?.toUpperCase()}</span>
                  </div>
                  <button onClick={()=>{api.track({business_id:id,product_id:prod.id,event_type:"click",source:"products"}).catch(()=>{});api.createCheckout(prod.id).then(r=>{window.location.href=r.checkout_url;}).catch(()=>alert("Checkout not configured yet."));}} style={{width:"100%",padding:"13px",borderRadius:12,border:"none",cursor:"pointer",fontWeight:700,fontSize:15,fontFamily:"inherit",background:`linear-gradient(135deg,${scheme.primary},${scheme.dark})`,color:"#fff",boxShadow:`0 4px 16px ${scheme.glow}`}}>
                    {biz.cta_text}
                  </button>
                </div>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* PRICING */}
      {pricingTiers.length>0&&(
        <section id="pricing" style={{background:"#f8fafc",padding:"80px 24px"}}>
          <div style={{maxWidth:1100,margin:"0 auto"}}>
            <p style={{textAlign:"center",fontSize:11,fontWeight:700,letterSpacing:"0.1em",textTransform:"uppercase",color:"#94a3b8",marginBottom:12}}>Pricing</p>
            <h2 style={{textAlign:"center",fontSize:"clamp(24px,3vw,36px)",fontWeight:800,color:"#0f172a",margin:"0 0 8px"}}>Simple, transparent pricing</h2>
            <p style={{textAlign:"center",fontSize:16,color:"#64748b",margin:"0 0 48px"}}>No hidden fees. Cancel anytime.</p>
            <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(280px,1fr))",gap:20,alignItems:"start"}}>
              {pricingTiers.map((tier:any,i:number)=>(
                <div key={i} style={{background:"#fff",borderRadius:20,border:tier.highlighted?`2px solid ${scheme.primary}`:"1px solid #e2e8f0",padding:"32px 28px",position:"relative",boxShadow:tier.highlighted?`0 8px 40px ${scheme.glow}`:"0 2px 12px rgba(0,0,0,0.04)"}}>
                  {tier.highlighted&&<div style={{position:"absolute",top:-14,left:"50%",transform:"translateX(-50%)",background:`linear-gradient(135deg,${scheme.primary},${scheme.dark})`,color:"#fff",fontSize:11,fontWeight:800,padding:"5px 16px",borderRadius:99,whiteSpace:"nowrap"}}>Most Popular</div>}
                  <p style={{fontSize:13,fontWeight:700,color:"#94a3b8",margin:"0 0 8px",textTransform:"uppercase",letterSpacing:"0.06em"}}>{tier.name}</p>
                  <div style={{display:"flex",alignItems:"baseline",gap:4,marginBottom:6}}>
                    <span style={{fontSize:42,fontWeight:900,color:"#0f172a"}}>{tier.price}</span>
                    <span style={{fontSize:14,color:"#94a3b8"}}>/{tier.period}</span>
                  </div>
                  <div style={{borderTop:"1px solid #f1f5f9",margin:"20px 0",paddingTop:20,display:"flex",flexDirection:"column",gap:10}}>
                    {(tier.features||[]).map((feat:string,j:number)=>(
                      <div key={j} style={{display:"flex",alignItems:"flex-start",gap:8,fontSize:14,color:"#374151"}}>
                        <Check size={15} style={{color:scheme.primary,flexShrink:0,marginTop:1}}/>{feat}
                      </div>
                    ))}
                  </div>
                  <button onClick={()=>{if(products[i]){api.track({business_id:id,product_id:products[i].id,event_type:"click",source:"pricing"}).catch(()=>{});api.createCheckout(products[i].id).then(r=>{window.location.href=r.checkout_url;}).catch(()=>alert("Checkout not configured yet."));}}} style={{width:"100%",padding:"13px",borderRadius:12,border:"none",cursor:"pointer",fontWeight:700,fontSize:15,fontFamily:"inherit",background:tier.highlighted?`linear-gradient(135deg,${scheme.primary},${scheme.dark})`:"#f8fafc",color:tier.highlighted?"#fff":"#374151",boxShadow:tier.highlighted?`0 4px 16px ${scheme.glow}`:"none"}}>
                    {tier.cta||biz.cta_text}
                  </button>
                </div>
              ))}
            </div>
          </div>
        </section>
      )}
      {/* FAQ */}
      {faq.length>0&&(
        <section style={{background:"#fff",padding:"80px 24px"}}>
          <div style={{maxWidth:720,margin:"0 auto"}}>
            <p style={{textAlign:"center",fontSize:11,fontWeight:700,letterSpacing:"0.1em",textTransform:"uppercase",color:"#94a3b8",marginBottom:12}}>FAQ</p>
            <h2 style={{textAlign:"center",fontSize:"clamp(24px,3vw,36px)",fontWeight:800,color:"#0f172a",margin:"0 0 40px"}}>Common questions</h2>
            <div style={{display:"flex",flexDirection:"column",gap:10}}>
              {faq.map((item:any,i:number)=>(
                <div key={i} style={{background:"#f8fafc",borderRadius:14,border:"1px solid #e2e8f0",overflow:"hidden"}}>
                  <button onClick={()=>setOpenFaq(openFaq===i?null:i)} style={{width:"100%",display:"flex",alignItems:"center",justifyContent:"space-between",padding:"18px 20px",background:"none",border:"none",cursor:"pointer",textAlign:"left",fontFamily:"inherit"}}>
                    <span style={{fontSize:15,fontWeight:700,color:"#0f172a"}}>{item.question}</span>
                    {openFaq===i?<ChevronUp size={18} style={{color:scheme.primary,flexShrink:0}}/>:<ChevronDown size={18} style={{color:"#94a3b8",flexShrink:0}}/>}
                  </button>
                  {openFaq===i&&<div style={{padding:"0 20px 18px",fontSize:14,color:"#64748b",lineHeight:1.7}}>{item.answer}</div>}
                </div>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* FINAL CTA */}
      <section style={{background:`linear-gradient(135deg,${scheme.primary} 0%,${scheme.dark} 100%)`,padding:"80px 24px",textAlign:"center"}}>
        <div style={{maxWidth:600,margin:"0 auto"}}>
          <h2 style={{fontSize:"clamp(28px,4vw,44px)",fontWeight:900,color:"#fff",margin:"0 0 16px",lineHeight:1.2}}>Ready to get started?</h2>
          <p style={{fontSize:17,color:"rgba(255,255,255,0.75)",margin:"0 0 32px",lineHeight:1.6}}>Join {biz.target_audience} already using {biz.name}.</p>
          <a href="#pricing" style={{display:"inline-flex",alignItems:"center",gap:8,background:"#fff",color:scheme.primary,fontWeight:800,fontSize:16,padding:"15px 32px",borderRadius:14,textDecoration:"none",boxShadow:"0 8px 30px rgba(0,0,0,0.2)"}}>
            {biz.cta_text} <ArrowRight size={18}/>
          </a>
          {trustBadges.length>0&&(
            <div style={{display:"flex",gap:20,justifyContent:"center",flexWrap:"wrap",marginTop:20}}>
              {trustBadges.map((b:string)=>(<span key={b} style={{display:"flex",alignItems:"center",gap:5,fontSize:12,color:"rgba(255,255,255,0.65)"}}><Check size={12}/> {b}</span>))}
            </div>
          )}
        </div>
      </section>

      {/* FOOTER */}
      <footer style={{background:"#0f172a",padding:"28px 24px",display:"flex",alignItems:"center",justifyContent:"space-between",flexWrap:"wrap",gap:12}}>
        <p style={{fontSize:13,color:"rgba(255,255,255,0.35)",margin:0}}>© {new Date().getFullYear()} {biz.name}. Built with AI Business Builder.</p>
        <div style={{display:"flex",gap:16}}>
          <Link href="/dashboard" style={{fontSize:13,color:"rgba(255,255,255,0.4)",textDecoration:"none"}}>Dashboard</Link>
          <Link href="/generator" style={{fontSize:13,color:"rgba(255,255,255,0.4)",textDecoration:"none"}}>Create another</Link>
        </div>
      </footer>
    </div>
  );
}
