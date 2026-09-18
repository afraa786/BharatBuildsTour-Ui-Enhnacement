import React from 'react';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

interface IPhoneFrameProps {
  children: React.ReactNode;
  className?: string;
  headerTitle?: string;
  headerSubtitle?: string;
  theme?: 'light' | 'dark' | 'manager';
}

export function IPhoneFrame({ children, className, headerTitle, headerSubtitle, theme = 'light' }: IPhoneFrameProps) {
  const isManager = theme === 'manager';
  
  return (
    <div className={cn(
      "relative mx-auto border-[6px] border-gray-900 rounded-[2.5rem] h-[600px] w-[300px] shadow-2xl overflow-hidden bg-white flex flex-col group",
      className
    )}>
      {/* Dynamic Island / Notch area */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[110px] h-[26px] bg-gray-900 rounded-b-[18px] z-20 flex justify-center items-center">
         <div className="w-12 h-[3px] rounded-full bg-black/30 mt-1"></div>
         <div className="w-[6px] h-[6px] rounded-full bg-[#1c1c1c] absolute right-4 mt-1 border-[1.5px] border-[#2a2a2a]"></div>
      </div>
      
      {/* Header */}
      <div className={cn(
        "pt-10 pb-3 px-4 z-10 border-b shadow-sm relative",
        isManager ? 'bg-[#F8FAFF] border-[#E9E2FF] text-[#182235]' : 'bg-[#075e54] text-white border-[#075e54]'
      )}>
        <div className="flex items-center justify-between">
          <div className="flex flex-col items-center w-full mt-1">
             <span className="text-[15px] font-semibold tracking-tight">{headerTitle}</span>
             {headerSubtitle && <span className="text-[11px] opacity-80 mt-0.5">{headerSubtitle}</span>}
          </div>
        </div>
      </div>

      {/* Screen Content */}
      <div className={cn(
        "flex-1 overflow-y-auto relative scroll-smooth scrollbar-hide",
        isManager ? 'bg-[#F8FAFF]' : 'bg-[#e5ddd5]'
      )}>
        {/* Chat Background Pattern Simulation */}
        {!isManager && (
          <div className="absolute inset-0 z-0 opacity-[0.05] pointer-events-none" 
               style={{ backgroundImage: 'radial-gradient(circle, #000 1px, transparent 1px)', backgroundSize: '20px 20px' }} 
          />
        )}
        <div className="relative z-10 flex flex-col p-3.5 space-y-3.5 pb-8">
          {children}
        </div>
      </div>
      
      {/* Footer fake input */}
      <div className={cn(
        "h-[64px] border-t flex items-center px-3 gap-2 z-10 relative bg-[#f0f0f0] border-gray-300",
        isManager && 'bg-white border-[#E9E2FF]'
      )}>
        {isManager ? (
           <>
              <div className="flex-1 flex justify-around items-center text-[#667085]">
                <div className="flex flex-col items-center gap-1 text-[#5b5bf7]">
                  <div className="w-5 h-5 bg-[#5b5bf7]/10 rounded-full flex items-center justify-center">
                    <div className="w-2.5 h-2.5 bg-[#5b5bf7] rounded-full"></div>
                  </div>
                  <span className="text-[9px] font-medium">Home</span>
                </div>
                <div className="flex flex-col items-center gap-1">
                  <div className="w-5 h-5 rounded-full border-2 border-current"></div>
                  <span className="text-[9px] font-medium">Alerts</span>
                </div>
                <div className="flex flex-col items-center gap-1">
                  <div className="w-5 h-5 flex flex-col gap-[3px] items-center justify-center">
                    <div className="w-4 h-[2px] bg-current rounded-full"></div>
                    <div className="w-4 h-[2px] bg-current rounded-full"></div>
                    <div className="w-4 h-[2px] bg-current rounded-full"></div>
                  </div>
                  <span className="text-[9px] font-medium">Menu</span>
                </div>
              </div>
           </>
        ) : (
           <>
            <div className="w-6 h-6 rounded-full text-blue-500 flex items-center justify-center font-bold text-2xl mb-1">+</div>
            <div className="flex-1 bg-white border border-gray-300 rounded-full h-10 flex items-center px-4 text-[13px] text-gray-400">
              Message
            </div>
            <div className="w-9 h-9 bg-[#00a884] rounded-full flex items-center justify-center text-white text-xs shrink-0">
              <svg className="w-4 h-4 ml-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" /></svg>
            </div>
           </>
        )}
      </div>
    </div>
  );
}
