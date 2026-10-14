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

/**
 * For Radix `onCloseAutoFocus`: runs the caller's handler, then skips the hand-back after a pointer.
 *
 * Radix hands focus back to whatever had it when the layer mounted. Where that is not what opened
 * it, `opener` names the element: the inspector focuses its own panel before Radix looks, so
 * Radix "returned" focus to a panel that was gone and it fell to the page body.
 */
export function keyboardFocusReturn(own?: (e: Event) => void, opener?: () => HTMLElement | null) {
  return (e: Event) => {
    own?.(e)
    const el = opener?.()
    if (lastInputWasPointer) e.preventDefault()
    else if (el?.isConnected) {
      e.preventDefault()
      el.focus({ preventScroll: true })
    }
  }
}
