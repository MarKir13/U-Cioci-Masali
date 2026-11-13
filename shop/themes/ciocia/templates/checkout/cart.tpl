{**
 * Cart page: Classic's template with the summary column of the source (issue #44): the heading
 * "Podsumowanie zamówienia" above the summary card, and the trust card under it in place of the
 * disabled Customer Reassurance module.
 *}
{extends file='parent:checkout/cart.tpl'}

{* "Kontynuuj zakupy" moved between the products and the info box: see _partials/cart-detailed.tpl. *}
{block name='continue_shopping'}{/block}

{* As on the source, the heading stands above the summary card, not inside it. *}
{block name='cart_summary'}
  <h2 class="ciocia-summary-title">Podsumowanie zamówienia</h2>
  {$smarty.block.parent}
{/block}

{block name='hook_reassurance'}
  {include file='_partials/summary-trust.tpl'}
  {$smarty.block.parent}
{/block}
