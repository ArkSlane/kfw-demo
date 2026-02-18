import React from "react";
import { useDemoSettings } from "@/lib/DemoSettingsContext";

export default function DemoOverlay() {
  const { demoBannerEnabled } = useDemoSettings();

  if (!demoBannerEnabled) return null;

  return (
    <>
      <div aria-hidden="true" className="pointer-events-none fixed inset-x-0 top-0 z-[9999] flex justify-center">
        <div className="pointer-events-none w-full bg-red-600/40 text-white text-3xl sm:text-4xl md:text-5xl font-extrabold tracking-wider py-3 select-none flex justify-center items-center">
          DEMO
        </div>
      </div>

      <div aria-hidden="true" className="pointer-events-none fixed inset-x-0 bottom-0 z-[9999] flex justify-center">
        <div className="pointer-events-none w-full bg-red-600/40 text-white text-3xl sm:text-4xl md:text-5xl font-extrabold tracking-wider py-3 select-none flex justify-center items-center">
          DEMO
        </div>
      </div>
    </>
  );
}
