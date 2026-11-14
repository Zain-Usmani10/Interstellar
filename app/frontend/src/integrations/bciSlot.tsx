/**
 * Insertion boundary for Affan's optional BCI widget (`app/frontend/src/bci/`).
 * Affan owns that folder. This file stays under Cursor ownership and only
 * reserves a mount point — no EEG classifier, no flashing stimuli here.
 */
export function BciSlot() {
  return (
    <div className="bci-slot" data-bci-slot="reserved" hidden aria-hidden>
      {/* Affan: mount optional widget from ../bci/ when ready */}
    </div>
  );
}
