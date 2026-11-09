{**
 * Adapted from ps_searchbar, copyright 2007-2020 PrestaShop SA and Contributors.
 * Licensed under the Academic Free License 3.0 (AFL-3.0).
 * https://opensource.org/licenses/AFL-3.0
 *}
<div id="search_widget" class="search-widgets" data-search-controller-url="{$search_controller_url|escape:'htmlall':'UTF-8'}">
  <form method="get" action="{$search_controller_url|escape:'htmlall':'UTF-8'}">
    <input type="hidden" name="controller" value="search">
    <input type="text" name="s" value="{$search_string|escape:'htmlall':'UTF-8'}" placeholder="Szukaj produktów…" aria-label="{l s='Search' d='Shop.Theme.Catalog'}">
    <i class="material-icons clear" aria-hidden="true">clear</i>
    <button class="ciocia-search-submit" type="submit" aria-label="{l s='Search' d='Shop.Theme.Catalog'}">
      <i class="material-icons" aria-hidden="true">search</i>
    </button>
  </form>
</div>
