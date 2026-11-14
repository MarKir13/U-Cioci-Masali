{**
 * Adapted from Classic, copyright since 2007 PrestaShop SA and Contributors.
 * Licensed under the Academic Free License 3.0 (AFL-3.0).
 * https://opensource.org/licenses/AFL-3.0
 *
 * Category header as on the source (issue #75): the name, the description and the subcategories as a row
 * of rounded links. The description shows on the first page only, as in Classic; the name and the
 * subcategories on every page.
 * Phones, as on the source: the description is cut to four lines with "Czytaj więcej", and only the
 * first six subcategories show, with "Pokaż wszystkie (N)" for the rest. custom.js runs both buttons and
 * marks each block with .is-ready; the CSS folds a block only then, so without JavaScript the description
 * and all subcategories show in full.
 * PrestaShop renders this file again after sorting or changing the page (CategoryController,
 * rendered_products_header), so the buttons keep no state outside it.
 *}
<div id="js-product-list-header" class="ciocia-listing__header">
  <h1 class="ciocia-listing__title">{$category.name}</h1>

  {if $listing.pagination.items_shown_from == 1 && $category.description}
    <div class="ciocia-category-description js-ciocia-category-description">
      <div id="category-description" class="ciocia-category-description__text">{$category.description nofilter}</div>
      <button type="button" class="ciocia-more-button ciocia-category-description__toggle" aria-controls="category-description" aria-expanded="false" data-more-label="Czytaj więcej" data-less-label="Zwiń" hidden>Czytaj więcej</button>
    </div>
  {/if}

  {if !empty($subcategories) && (!isset($display_subcategories) || $display_subcategories eq 1)}
    {$ciocia_visible_subcategories = 6}
    <nav class="ciocia-subcategories js-ciocia-subcategories{if $subcategories|count > $ciocia_visible_subcategories} ciocia-subcategories--collapsible{/if}" aria-label="Podkategorie">
      <ul id="ciocia-subcategories-list" class="ciocia-subcategories__list">
        {foreach from=$subcategories item=subcategory}
          <li class="ciocia-subcategories__item">
            <a class="ciocia-subcategories__link" href="{$subcategory.url}">{$subcategory.name}</a>
          </li>
        {/foreach}
      </ul>
      {if $subcategories|count > $ciocia_visible_subcategories}
        <button type="button" class="ciocia-more-button ciocia-subcategories__toggle" aria-controls="ciocia-subcategories-list" aria-expanded="false" data-more-label="Pokaż wszystkie ({$subcategories|count})" data-less-label="Pokaż mniej">Pokaż wszystkie ({$subcategories|count})</button>
      {/if}
    </nav>
  {/if}
</div>
