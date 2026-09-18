import React from 'react';
import { IPhoneFrame } from './iphone-frame';
import { ChatBubble, QuoteCard, PaymentCard, ManagerCard } from './chat-bubbles';
import { ArrowRight, Play, AlertCircle, TrendingUp, Clock, Package } from 'lucide-react';

export function Hero() {
  return (
    <section className="relative pt-32 pb-20 overflow-hidden bg-[#F8FAFF]">
      {/* Soft blurred radial gradients for the premium feel */}
      <div className="absolute top-1/4 left-1/4 w-[500px] h-[500px] bg-[#DFF3FF] rounded-full blur-[100px] opacity-70 -z-10 mix-blend-multiply pointer-events-none"></div>
      <div className="absolute bottom-1/4 right-1/4 w-[600px] h-[600px] bg-[#E9E2FF] rounded-full blur-[120px] opacity-60 -z-10 mix-blend-multiply pointer-events-none"></div>
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[400px] bg-white rounded-[100%] blur-[80px] opacity-80 -z-10 pointer-events-none"></div>

      <div className="max-w-[1300px] mx-auto px-6 relative z-10">
        
        {/* Desktop Layout: Left Phone | Center Content | Right Phone */}
        <div className="flex flex-col lg:flex-row items-center justify-between gap-12 lg:gap-8">
          
          {/* Mobile Order 1: Center Content */}
          <div className="lg:order-2 flex-1 flex flex-col items-center text-center max-w-[600px] mx-auto z-20">
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-[#E9E2FF]/80 text-[#5b5bf7] font-semibold text-[11px] tracking-widest uppercase mb-8 border border-[#5b5bf7]/20">
              <span className="w-1.5 h-1.5 rounded-full bg-[#5b5bf7] animate-pulse"></span>
              AI For Your Wholesale Business
            </div>
            
            <h1 className="text-[44px] md:text-[56px] lg:text-[64px] font-bold text-[#182235] leading-[1.05] tracking-[-0.03em] mb-6">
              Your WhatsApp<br />
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-[#5b5bf7] to-[#8b5cf6]">Sales Assistant</span><br />
              for Wholesale Business.
            </h1>
            
            <p className="text-[18px] md:text-[20px] text-[#667085] leading-relaxed mb-10 max-w-[480px]">
              From customer message to payment — StockAware handles the workflow.
            </p>
            
            <div className="flex flex-col sm:flex-row items-center gap-4 w-full justify-center">
              <button className="w-full sm:w-auto px-8 py-3.5 bg-[#182235] hover:bg-[#2a364a] text-white rounded-full font-semibold text-[15px] shadow-lg shadow-[#182235]/15 transition-all flex items-center justify-center gap-2 group">
                See how it works
                <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
              </button>
              <button className="w-full sm:w-auto px-8 py-3.5 bg-white hover:bg-gray-50 border border-gray-200 text-[#182235] rounded-full font-semibold text-[15px] transition-all flex items-center justify-center gap-2 shadow-sm">
                <Play className="w-4 h-4 fill-current" />
                Talk to StockAware
              </button>
            </div>
            
            <p className="text-[13px] text-[#667085] mt-6 font-medium">
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
                    <div className="bg-white border border-[#E9E2FF] rounded-lg p-2.5 shadow-sm">
                      <TrendingUp className="w-4 h-4 text-[#059669] mb-1" />
                      <div className="text-[10px] text-[#667085] font-medium">Sales</div>
                      <div className="text-[14px] font-bold text-[#182235]">₹1.84L</div>
                    </div>
                    <div className="bg-white border border-[#E9E2FF] rounded-lg p-2.5 shadow-sm">
                      <Package className="w-4 h-4 text-[#5b5bf7] mb-1" />
                      <div className="text-[10px] text-[#667085] font-medium">Orders</div>
                      <div className="text-[14px] font-bold text-[#182235]">24</div>
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
                  <button className="bg-[#5b5bf7] text-white text-[12px] font-medium px-4 py-1.5 rounded-full">Yes, remind</button>
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
