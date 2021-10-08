import Hero from "./components/home/Hero";
import WhatIs from "./components/home/WhatIs";
import Features from "./components/home/Features";
import Developers from "./components/home/Developers";

export default function Home() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <Hero />
      <WhatIs />
      <Features />
      <Developers />
    </div>
  );
}
