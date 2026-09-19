import React from 'react';
import { IPhoneFrame } from './iphone-frame';
import { ChatBubble, QuoteCard, PaymentCard, ManagerCard } from './chat-bubbles';
import { ArrowRight, Play, AlertCircle, TrendingUp, Clock, Package } from 'lucide-react';

export function Hero() {
  return (
    <section className="relative overflow-hidden bg-[#F7F4ED] pt-20 pb-20 [perspective:1500px]">
      {/* Soft blurred radial gradients for the premium feel */}
      <div className="absolute top-1/4 left-1/4 w-[500px] h-[500px] bg-[#C7D3C0] rounded-full blur-[100px] opacity-70 -z-10 mix-blend-multiply pointer-events-none"></div>
      <div className="absolute bottom-1/4 right-1/4 w-[600px] h-[600px] bg-[#C7D3C0] rounded-full blur-[120px] opacity-60 -z-10 mix-blend-multiply pointer-events-none"></div>
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[400px] bg-white rounded-[100%] blur-[80px] opacity-80 -z-10 pointer-events-none"></div>
      <div className="pointer-events-none absolute inset-0 opacity-30 [background-image:linear-gradient(to_right,rgba(36,48,42,0.06)_1px,transparent_1px),linear-gradient(to_bottom,rgba(36,48,42,0.06)_1px,transparent_1px)] [background-size:60px_60px] [mask-image:radial-gradient(ellipse_at_center,black,transparent_72%)]" aria-hidden="true" />

      <div className="relative z-10 mx-auto max-w-[1300px] px-6">
        
        {/* Desktop Layout: Left Phone | Center Content | Right Phone */}
        <div className="relative flex flex-col items-center justify-between gap-12 rounded-[32px] border border-[#C7D3C0]/70 bg-white/25 px-4 py-10 shadow-[0_30px_90px_rgba(36,48,42,0.08)] backdrop-blur-[2px] lg:flex-row lg:gap-8 lg:px-8">
          <div className="pointer-events-none absolute inset-3 rounded-[24px] border border-white/60" aria-hidden="true" />
          
          {/* Mobile Order 1: Center Content */}
          <div className="lg:order-2 flex-1 flex flex-col items-center text-center max-w-[600px] mx-auto z-20">
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-[#C7D3C0]/80 text-[#8FA28A] font-semibold text-[11px] tracking-widest uppercase mb-8 border border-[#8FA28A]/20">
              <span className="w-1.5 h-1.5 rounded-full bg-[#8FA28A] animate-pulse"></span>
              AI For Your Wholesale Business
            </div>
            
            <h1 className="text-[44px] md:text-[56px] lg:text-[64px] font-bold text-[#24302A] leading-[1.05] tracking-[-0.03em] mb-6">
              Your WhatsApp<br />
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-[#8FA28A] to-[#8b5cf6]">Sales Assistant</span><br />
              for Wholesale Business.
            </h1>
            
            <p className="text-[18px] md:text-[20px] text-[#667267] leading-relaxed mb-10 max-w-[480px]">
              From customer message to payment — StockAware handles the workflow.
            </p>
            
            <div className="flex flex-col sm:flex-row items-center gap-4 w-full justify-center">
              <button className="w-full sm:w-auto px-8 py-3.5 bg-[#24302A] hover:bg-[#2a364a] text-white rounded-full font-semibold text-[15px] shadow-lg shadow-[#24302A]/15 transition-all flex items-center justify-center gap-2 group">
                See how it works
                <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
              </button>
              <button className="w-full sm:w-auto px-8 py-3.5 bg-white hover:bg-gray-50 border border-gray-200 text-[#24302A] rounded-full font-semibold text-[15px] transition-all flex items-center justify-center gap-2 shadow-sm">
                <Play className="w-4 h-4 fill-current" />
                Talk to StockAware
              </button>
            </div>
            
            <p className="text-[13px] text-[#667267] mt-6 font-medium">
              No new software for your customers. Just WhatsApp.
            </p>
          </div>

          {/* Manager Phone (Left on Desktop, below Content on Mobile) */}
          <div className="lg:order-1 relative lg:-mr-12 xl:-mr-16 animate-[float_6s_ease-in-out_infinite]">
            <IPhoneFrame 
              theme="manager" 
              headerTitle="Manager Assistant"
              headerSubtitle="Active now"
              className="transform lg:-rotate-6 scale-[0.85] sm:scale-90 lg:scale-100 origin-center"
            >
              <div className="flex flex-col h-full justify-end">
                <ChatBubble role="agent" isManager>
                  Good morning, Aamir 👋
                </ChatBubble>
                <ChatBubble role="agent" isManager>
                  Here's what happened yesterday.
                </ChatBubble>
                <ChatBubble role="agent" isManager className="!bg-transparent !p-0 !border-0 !shadow-none">
                  <div className="grid grid-cols-2 gap-2 mt-1 mb-2">
                    <div className="bg-white border border-[#C7D3C0] rounded-lg p-2.5 shadow-sm">
                      <TrendingUp className="w-4 h-4 text-[#059669] mb-1" />
                      <div className="text-[10px] text-[#667267] font-medium">Sales</div>
                      <div className="text-[14px] font-bold text-[#24302A]">₹1.84L</div>
                    </div>
                    <div className="bg-white border border-[#C7D3C0] rounded-lg p-2.5 shadow-sm">
                      <Package className="w-4 h-4 text-[#8FA28A] mb-1" />
                      <div className="text-[10px] text-[#667267] font-medium">Orders</div>
                      <div className="text-[14px] font-bold text-[#24302A]">24</div>
                    </div>
                  </div>
                </ChatBubble>
                <ChatBubble role="agent" isManager>
                  Your attention today:
                </ChatBubble>
                <ChatBubble role="agent" isManager className="!bg-transparent !p-0 !border-0 !shadow-none gap-0">
                  <ManagerCard icon="⚠️" title="Low Stock" value={<>MCB32 <span className="font-normal text-gray-500">• 8 units left</span></>} variant="alert" />
                  <ManagerCard icon="💳" title="Pending Payments" value={<>3 customers <span className="font-normal text-gray-500">• ₹42,500</span></>} />
                </ChatBubble>
                <ChatBubble role="agent" isManager className="mt-4">
                  Want me to remind the 3 customers with pending payments?
                </ChatBubble>
                <div className="flex gap-2 justify-end mt-2">
                  <button className="bg-[#8FA28A] text-white text-[12px] font-medium px-4 py-1.5 rounded-full">Yes, remind</button>
                </div>
              </div>
            </IPhoneFrame>
            {/* Soft decorative shadow below phone */}
            <div className="absolute -bottom-6 left-1/2 -translate-x-1/2 w-[200px] h-[30px] bg-black/10 blur-xl rounded-full"></div>
          </div>

          {/* Sales Phone (Right on Desktop, below Manager Phone on Mobile) */}
          <div className="lg:order-3 relative lg:-ml-12 xl:-ml-16 animate-[float_7s_ease-in-out_infinite_0.5s]">
            <IPhoneFrame 
              theme="light" 
              headerTitle="StockAware Sales"
              headerSubtitle="business account"
              className="transform lg:rotate-6 scale-[0.85] sm:scale-90 lg:scale-100 origin-center"
            >
              <ChatBubble role="customer" time="09:24 AM">
                Hi, I need 20 pieces of 32A MCB.
              </ChatBubble>
              <ChatBubble role="agent" time="09:24 AM">
                Sure! We have 8 pieces available right now.<br/><br/>
                Would you like me to check the next stock arrival or prepare a quote for 8 pieces?
              </ChatBubble>
              <ChatBubble role="customer" time="09:26 AM">
                Prepare for 8 pieces only.
              </ChatBubble>
              <ChatBubble role="agent" time="09:26 AM">
                Got it. I've prepared your quote.
              </ChatBubble>
              <QuoteCard quantity={8} product="32A MCB" total="₹3,600" />
              <ChatBubble role="agent" time="09:27 AM">
                Your quote is ready. Here's the payment link to confirm your order.
              </ChatBubble>
              <PaymentCard total="₹3,600" />
            </IPhoneFrame>
            <div className="absolute -bottom-6 left-1/2 -translate-x-1/2 w-[200px] h-[30px] bg-black/10 blur-xl rounded-full"></div>
          </div>

        </div>
      </div>
    </section>
  );
}
