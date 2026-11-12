{**
 * Cart page: Classic's template with the summary card of the source (issue #44): the heading
 * "Podsumowanie zamówienia" on the card, and the trust card under it in place of the disabled
 * Customer Reassurance module.
 *}
{extends file='parent:checkout/cart.tpl'}

{block name='hook_shopping_cart'}
  <h2 class="ciocia-summary-title">Podsumowanie zamówienia</h2>
  {$smarty.block.parent}
{/block}

{block name='hook_reassurance'}
  {include file='_partials/summary-trust.tpl'}
  {$smarty.block.parent}
{/block}
