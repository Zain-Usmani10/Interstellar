import { useEffect, useRef } from "react";
import { useFrame, useThree } from "@react-three/fiber";

/** Opt-in development probe: measures actual scene frames, never mission time. */
export function ScenePerformance({ onSample }: { onSample: (report: string) => void }) {
  const samples = useRef<number[]>([]);
  const warmup = useRef(0);
  const elapsed = useRef(0);
  const { size, gl } = useThree();
  useEffect(() => {
    const reset = () => {
      samples.current = [];
      elapsed.current = 0;
      warmup.current = 0;
    };
    reset();
    document.addEventListener("visibilitychange", reset);
    return () => document.removeEventListener("visibilitychange", reset);
  }, [size.width, size.height]);
  useFrame((_, delta) => {
    warmup.current += delta;
    if (warmup.current < 5) return;
    samples.current.push(delta * 1000);
    elapsed.current += delta;
    if (elapsed.current < 15) return;
    const sorted = [...samples.current].sort((a, b) => a - b);
    const report = {
      fps: Number((samples.current.length / elapsed.current).toFixed(1)),
      p95_frame_ms: Number(sorted[Math.floor(sorted.length * 0.95)].toFixed(1)),
      frames: samples.current.length,
      seconds: Number(elapsed.current.toFixed(2)),
      viewport: `${window.innerWidth}x${window.innerHeight}`,
      canvas: `${size.width}x${size.height}`,
      pixel_ratio: gl.getPixelRatio(),
      renderer: gl.getContext().getParameter(gl.getContext().RENDERER),
    };
    onSample(JSON.stringify(report, null, 2));
    samples.current = [];
    elapsed.current = 0;
  });
  return null;
}
