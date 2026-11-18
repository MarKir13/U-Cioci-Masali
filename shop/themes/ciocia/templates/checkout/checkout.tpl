{**
 * Checkout page: Classic's template plus the steps bar (issue #44).
 *
 * As on the source, the bar is its own card above the card with the steps and the summary, so it goes
 * in the layout's notifications block, the last one before that card; its own .container gives it the
 * card's width. Not the breadcrumb block: breadcrumb.tpl has an inner block of the same name, so the
 * bar would be printed twice.
 * custom.js fills the list and the [data-steps-*] fields from the step sections, so they always show
 * the same state as Classic's checkout script, which switches steps in the browser without a reload.
 * Phones get the compact form of the source instead of the list: a progress ring "1 / 4", the current
 * step and the next one.
 * data-back-<step id>: label of the "Wróć do ..." button that custom.js puts in the step after that one.
 *}
{extends file='parent:checkout/checkout.tpl'}

{* The trust card under the summary, as on the source and on the cart page. *}
{block name='cart_summary'}
  {$smarty.block.parent}
  {include file='_partials/summary-trust.tpl'}
{/block}

{block name='notifications'}
  {$smarty.block.parent}
  <div class="container">
    <nav class="ciocia-steps" aria-label="Etapy zamówienia" data-complete-label="krok ukończony"
         data-back-checkout-personal-information-step="Wróć do danych osobowych"
         data-back-checkout-addresses-step="Wróć do adresów"
         data-back-checkout-delivery-step="Wróć do sposobu dostawy"
         hidden>
      <ol class="ciocia-steps__list"></ol>
      <div class="ciocia-steps__compact">
        <span class="ciocia-steps__ring">
          <span class="sr-only">Krok</span>
          <span data-steps-position></span><span aria-hidden="true"> / </span><span class="sr-only">z</span>
          <span data-steps-count></span>
        </span>
        <span class="ciocia-steps__summary">
          <span class="ciocia-steps__current" data-steps-current></span>
          <span class="ciocia-steps__next" data-steps-next-row>Dalej: <span data-steps-next></span></span>
        </span>
      </div>
    </nav>
  </div>
{/block}
