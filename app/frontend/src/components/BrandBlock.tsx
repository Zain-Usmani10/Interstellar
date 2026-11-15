import { useState } from "react";

const ABOUT =
  "Interstellar is a live interplanetary transfer console: NASA-dated orbits, validated routes, and an FPGA or simulator controller. The browser never invents positions or plans ahead of the mission snapshot.";

export function BrandBlock() {
  const [open, setOpen] = useState(false);

  return (
    <header className="brand-block glass">
      <div className="brand-block-text">
        <p className="brand">Interstellar</p>
        <p className="brand-sub">Interplanetary TX</p>
      </div>
      <button
        type="button"
        className={open ? "about-toggle open" : "about-toggle"}
        aria-expanded={open}
        aria-controls="program-about"
        onClick={() => setOpen((v) => !v)}
      >
        About
      </button>
      {open ? (
        <p id="program-about" className="about-copy" role="note">
          {ABOUT}
        </p>
      ) : null}
    </header>
  );
}
