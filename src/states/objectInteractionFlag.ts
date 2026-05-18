/**
 * Mutable singleton flag used to distinguish a mousedown on a 3D object
 * (MovableObject's invisible bounding-box mesh) from a mousedown on empty
 * canvas space.
 *
 * MouseDragSelect reads this at mousedown time; if `active` is true, the
 * drag started on an object and the marquee selection is suppressed so that
 * the user can still click/drag individual furniture pieces normally.
 */
export const objectInteractionFlag = {
  active: false,
};
