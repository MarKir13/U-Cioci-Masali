{**
 * Adapted from Classic, copyright since 2007 PrestaShop SA and Contributors.
 * Licensed under the Academic Free License 3.0 (AFL-3.0).
 * https://opensource.org/licenses/AFL-3.0
 *
 * "Sortuj wg:" with a white button showing the current order, as on the source (issue #75).
 * Classic's dropdown is kept as it is (data-toggle="dropdown" on .products-sort-order, links with
 * .js-search-link), so Classic's scripts open it and load the new order without a reload.
 *
 * Four orders, as on the source: Polecane, Najnowsze, Cena: od najniższej, Cena: od najwyższej. PrestaShop
 * offers eight (sales, relevance, name, price, reference); the template keeps relevance (position) and the two
 * price orders under the source's names. "Najnowsze" is no order of the list, but PrestaShop sorts by any
 * "product.<field>.<way>" given in ?order=, so its link is the price link with the order swapped for
 * product.date_add.desc, and it counts as current when that is what ?order= holds.
 *}
{foreach from=$listing.sort_orders item=sort_order}
  {if $sort_order.field == 'position'}{assign var='ciocia_recommended' value=$sort_order}{/if}
  {if $sort_order.field == 'price' && $sort_order.direction == 'asc'}{assign var='ciocia_price_low' value=$sort_order}{/if}
  {if $sort_order.field == 'price' && $sort_order.direction == 'desc'}{assign var='ciocia_price_high' value=$sort_order}{/if}
{/foreach}
{assign var='ciocia_newest_current' value=false}
{if isset($smarty.get.order) && $smarty.get.order == 'product.date_add.desc'}{assign var='ciocia_newest_current' value=true}{/if}
{assign var='ciocia_recommended_current' value=false}
{if isset($ciocia_recommended) && $ciocia_recommended.current && !$ciocia_newest_current}{assign var='ciocia_recommended_current' value=true}{/if}
<div class="ciocia-sort">
  <span id="ciocia-sort-label" class="ciocia-sort__label">{l s='Sort by:' d='Shop.Theme.Global'}</span>
  <div class="products-sort-order dropdown ciocia-sort__dropdown">
    <button
      id="ciocia-sort-button"
      class="btn-unstyle select-title ciocia-sort__button"
      type="button"
      data-toggle="dropdown"
      aria-labelledby="ciocia-sort-label ciocia-sort-button"
      aria-haspopup="true"
      aria-expanded="false">
      {if $ciocia_newest_current}Najnowsze{elseif !empty($ciocia_price_low.current)}Cena: od najniższej{elseif !empty($ciocia_price_high.current)}Cena: od najwyższej{else}Polecane{/if}
      <i class="material-icons" aria-hidden="true">expand_more</i>
    </button>
    <div class="dropdown-menu ciocia-sort__menu">
      {if isset($ciocia_recommended)}
        <a rel="nofollow" href="{$ciocia_recommended.url}" class="select-list ciocia-sort__option {['current' => $ciocia_recommended_current, 'js-search-link' => true]|classnames}"{if $ciocia_recommended_current} aria-current="true"{/if}>Polecane</a>
      {/if}
      {if isset($ciocia_price_low)}
        <a rel="nofollow" href="{$ciocia_price_low.url|replace:'product.price.asc':'product.date_add.desc'}" class="select-list ciocia-sort__option {['current' => $ciocia_newest_current, 'js-search-link' => true]|classnames}"{if $ciocia_newest_current} aria-current="true"{/if}>Najnowsze</a>
        <a rel="nofollow" href="{$ciocia_price_low.url}" class="select-list ciocia-sort__option {['current' => $ciocia_price_low.current, 'js-search-link' => true]|classnames}"{if $ciocia_price_low.current} aria-current="true"{/if}>Cena: od najniższej</a>
      {/if}
      {if isset($ciocia_price_high)}
        <a rel="nofollow" href="{$ciocia_price_high.url}" class="select-list ciocia-sort__option {['current' => $ciocia_price_high.current, 'js-search-link' => true]|classnames}"{if $ciocia_price_high.current} aria-current="true"{/if}>Cena: od najwyższej</a>
      {/if}
    </div>
  </div>
</div>
