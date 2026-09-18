import React from 'react';
import { Navbar } from '@/components/landing/navbar';
import { Hero } from '@/components/landing/hero';
import { FeaturesSection } from '@/components/landing/features-section';
import { TwoAgentsSection } from '@/components/landing/two-agents-section';
import { LanguageSection } from '@/components/landing/language-section';
import { WorkflowSection } from '@/components/landing/workflow-section';
import { ControlRoomPreview } from '@/components/landing/control-room-preview';
import { RealBusinessSection } from '@/components/landing/real-business-section';
import { CTAFooter } from '@/components/landing/cta-footer';

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-[#F8FAFF] text-[#182235] font-sans overflow-x-hidden">
      <Navbar />
      <main>
        <Hero />
        <FeaturesSection />
        <TwoAgentsSection />
        <LanguageSection />
        <WorkflowSection />
        <ControlRoomPreview />
        <RealBusinessSection />
        <CTAFooter />
      </main>
    </div>
  );
}
