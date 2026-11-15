"use client";

import { useEffect, useRef } from "react";
import {
  PHASE_SECONDS,
  buildTrail,
  nextTarget,
  stepTrail,
  type Point,
  type Trail,
} from "@/lib/trail";

type Three = typeof import("three");

const INK = 0xf4f1ea;
const WIRE = 0x57534e;
const BAD = 0xff5a47;
const MEND = 0x6ee7b7;
const NODE_RADIUS = 0.017;

function start(
  THREE: Three,
  canvas: HTMLCanvasElement,
  still: boolean,
): () => void {
  const renderer = new THREE.WebGLRenderer({
    canvas,
    antialias: true,
    alpha: true,
    powerPreference: "low-power",
  });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  const scene = new THREE.Scene();
  const camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0.1, 10);
  camera.position.z = 2;

  let aspect = 1;
  let trail: Trail = buildTrail(aspect);
  const disc = new THREE.CircleGeometry(NODE_RADIUS, 24);
  const nodeMaterial = new THREE.MeshBasicMaterial({ color: INK });
  let nodes = new THREE.InstancedMesh(disc, nodeMaterial, 1);
  const wireGeometry = new THREE.BufferGeometry();
  const wires = new THREE.LineSegments(
    wireGeometry,
    new THREE.LineBasicMaterial({ color: WIRE }),
  );
  const strip = new THREE.Mesh(
    new THREE.PlaneGeometry(1, 1),
    new THREE.MeshBasicMaterial({ color: BAD, transparent: true }),
  );
  const marker = new THREE.Mesh(
    new THREE.RingGeometry(NODE_RADIUS * 1.9, NODE_RADIUS * 2.4, 32),
    new THREE.MeshBasicMaterial({ color: MEND, transparent: true }),
  );
  scene.add(wires, strip, marker);
  const placer = new THREE.Object3D();

  function rebuild(): void {
    const width = canvas.clientWidth || 1;
    const height = canvas.clientHeight || 1;
    aspect = width / height;
    renderer.setSize(width, height, false);
    camera.left = -aspect;
    camera.right = aspect;
    camera.updateProjectionMatrix();
    trail = buildTrail(aspect);
    scene.remove(nodes);
    nodes.dispose();
    nodes = new THREE.InstancedMesh(disc, nodeMaterial, trail.points.length);
    scene.add(nodes);
    for (let warm = 0; warm < 220; warm += 1) {
      stepTrail(trail, 1 / 60, null, false);
    }
  }

  function layStrip(
    from: Point,
    to: { x: number; y: number },
    colour: number,
    opacity: number,
    width: number,
  ): void {
    const dx = to.x - from.x;
    const dy = to.y - from.y;
    strip.visible = opacity > 0.01;
    strip.position.set((from.x + to.x) / 2, (from.y + to.y) / 2, 0.1);
    strip.rotation.z = Math.atan2(dy, dx);
    strip.scale.set(Math.hypot(dx, dy), width, 1);
    const material = strip.material as import("three").MeshBasicMaterial;
    material.color.setHex(colour);
    material.opacity = opacity;
  }

  function draw(): void {
    trail.points.forEach((point, index) => {
      placer.position.set(point.x, point.y, 0.2);
      placer.scale.setScalar(point.size);
      placer.updateMatrix();
      nodes.setMatrixAt(index, placer.matrix);
    });
    nodes.instanceMatrix.needsUpdate = true;
    const plain = trail.links.filter((link) => link !== trail.bridgeLink);
    const positions = new Float32Array(plain.length * 6);
    plain.forEach((link, index) => {
      const a = trail.points[link.a] as Point;
      const b = trail.points[link.b] as Point;
      positions.set([a.x, a.y, 0, b.x, b.y, 0], index * 6);
    });
    wireGeometry.setAttribute(
      "position",
      new THREE.BufferAttribute(positions, 3),
    );

    const end = trail.points[trail.bridgeEnd] as Point;
    const held = trail.points[trail.targets[trail.attached]] as Point;
    const wanted = trail.points[nextTarget(trail)] as Point;
    const progress = Math.min(1, trail.clock / PHASE_SECONDS[trail.phase]);
    const ringMaterial = marker.material as import("three").MeshBasicMaterial;
    marker.visible = false;
    if (trail.phase === "held") {
      layStrip(end, held, WIRE, 1, 0.004);
    } else if (trail.phase === "flagged") {
      layStrip(
        end,
        held,
        BAD,
        0.65 + 0.35 * Math.sin(progress * Math.PI * 6),
        0.007,
      );
    } else if (trail.phase === "free") {
      const stub = {
        x: end.x + (held.x - end.x) * 0.3,
        y: end.y + (held.y - end.y) * 0.3,
      };
      layStrip(end, stub, BAD, 1 - progress, 0.007);
      marker.visible = true;
      marker.position.set(wanted.x, wanted.y, 0.15);
      ringMaterial.opacity = progress;
    } else if (trail.phase === "forming") {
      const reach = {
        x: end.x + (wanted.x - end.x) * progress,
        y: end.y + (wanted.y - end.y) * progress,
      };
      layStrip(end, reach, MEND, 1, 0.007);
      marker.visible = true;
      marker.position.set(wanted.x, wanted.y, 0.15);
      ringMaterial.opacity = 1;
    } else {
      layStrip(end, held, MEND, 1 - 0.55 * progress, 0.007 - 0.003 * progress);
      marker.visible = true;
      marker.position.set(held.x, held.y, 0.15);
      ringMaterial.opacity = 1 - progress;
    }
    renderer.render(scene, camera);
  }

  let pointer: { x: number; y: number } | null = null;
  function onPointer(event: PointerEvent): void {
    const box = canvas.getBoundingClientRect();
    if (event.clientY < box.top || event.clientY > box.bottom) {
      pointer = null;
      return;
    }
    pointer = {
      x: (((event.clientX - box.left) / box.width) * 2 - 1) * aspect,
      y: -(((event.clientY - box.top) / box.height) * 2 - 1),
    };
  }
  function onLeave(): void {
    pointer = null;
  }

  rebuild();
  draw();
  if (still) {
    const onResize = () => {
      rebuild();
      draw();
    };
    window.addEventListener("resize", onResize);
    return () => {
      window.removeEventListener("resize", onResize);
      renderer.dispose();
    };
  }

  let frame = 0;
  let last = performance.now();
  let visible = true;
  function tick(now: number): void {
    frame = requestAnimationFrame(tick);
    if (!visible || document.hidden) {
      last = now;
      return;
    }
    stepTrail(trail, (now - last) / 1000, pointer, true);
    last = now;
    draw();
  }
  const watcher = new IntersectionObserver((entries) => {
    visible = entries.some((entry) => entry.isIntersecting);
  });
  watcher.observe(canvas);
  let resizing = 0;
  const onResize = () => {
    window.clearTimeout(resizing);
    resizing = window.setTimeout(rebuild, 150);
  };
  window.addEventListener("resize", onResize);
  window.addEventListener("pointermove", onPointer, { passive: true });
  window.addEventListener("pointerleave", onLeave);
  frame = requestAnimationFrame(tick);
  return () => {
    cancelAnimationFrame(frame);
    watcher.disconnect();
    window.removeEventListener("resize", onResize);
    window.removeEventListener("pointermove", onPointer);
    window.removeEventListener("pointerleave", onLeave);
    renderer.dispose();
  };
}

export function TrailCanvas() {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = ref.current;
    if (canvas === null) {
      return;
    }
    let cancelled = false;
    let stop: () => void = () => {};
    const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    void import("three").then((THREE) => {
      if (!cancelled) {
        stop = start(THREE, canvas, still);
      }
    });
    return () => {
      cancelled = true;
      stop();
    };
  }, []);

  return (
    <canvas
      ref={ref}
      aria-hidden="true"
      className="absolute inset-0 h-full w-full"
    />
  );
}
