{**
 * Adapted from Classic, copyright since 2007 PrestaShop SA and Contributors.
 * Licensed under the Academic Free License 3.0 (AFL-3.0).
 * https://opensource.org/licenses/AFL-3.0
 *
 * "Sortuj wg:" with a white button showing the current order, as on the source (issue #75).
 * Classic's dropdown is kept as it is (data-toggle="dropdown" on .products-sort-order, links with
 * .js-search-link), so Classic's scripts open it and load the new order without a reload.
 *}
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
      {if $listing.sort_selected}{$listing.sort_selected}{else}{l s='Choose' d='Shop.Theme.Actions'}{/if}
      <i class="material-icons" aria-hidden="true">expand_more</i>
    </button>
    <div class="dropdown-menu ciocia-sort__menu">
      {foreach from=$listing.sort_orders item=sort_order}
        <a
          rel="nofollow"
          href="{$sort_order.url}"
          class="select-list ciocia-sort__option {['current' => $sort_order.current, 'js-search-link' => true]|classnames}"
          {if $sort_order.current}aria-current="true"{/if}
        >
          {$sort_order.label}
        </a>
      {/foreach}
    </div>
  </div>
</div>
