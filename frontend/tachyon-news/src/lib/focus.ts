/*
  Menus, popovers and dialogs hand focus back to the button that opened them when they close.
  That's right for keyboards, but after a tap or click it leaves a focus ring on the button
  (browsers count the handed-back focus as keyboard focus; iOS draws it in system blue). So
  focus goes back only when the last input was a key.
*/
let lastInputWasPointer = false
if (typeof window !== 'undefined') {
  window.addEventListener('pointerdown', () => { lastInputWasPointer = true }, true)
  window.addEventListener('keydown', () => { lastInputWasPointer = false }, true)
}

/** For Radix `onCloseAutoFocus`: runs the caller's handler, then skips the hand-back after a pointer. */
export function keyboardFocusReturn(own?: (e: Event) => void) {
  return (e: Event) => {
    own?.(e)
    if (lastInputWasPointer) e.preventDefault()
  }
}
