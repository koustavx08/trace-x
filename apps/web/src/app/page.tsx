"use client";

import Navbar from "@/components/landing/Navbar";
import HeroSection from "@/components/landing/HeroSection";
import CorePrinciples from "@/components/landing/CorePrinciples";
import TeamSection from "@/components/landing/TeamSection";
import Footer from "@/components/landing/Footer";

export default function Home() {
  return (
    <div className="min-h-screen selection:bg-[#cf0] selection:text-black">
      <Navbar />
      <main className="pt-[65px]">
        <HeroSection />
        <CorePrinciples />
        <TeamSection />
      </main>
      <Footer />
    </div>
  );
}
