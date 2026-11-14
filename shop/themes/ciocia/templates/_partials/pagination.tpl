{**
 * Adapted from Classic, copyright since 2007 PrestaShop SA and Contributors.
 * Licensed under the Academic Free License 3.0 (AFL-3.0).
 * https://opensource.org/licenses/AFL-3.0
 *
 * Page links of product lists as on the source (issue #75): white rounded boxes, the current page in
 * burgundy, "Poprzedni" and "Następny" with arrows (only the arrows below 1200 px; the words stay for
 * screen readers). Under the products "Pokazano 1-12 z N pozycji" comes first, on the left.
 * catalog/_partials/products-top.tpl passes ciocia_position='top' for the copy above the products:
 * links only, and a label of its own, so the two navigation landmarks can be told apart.
 * Links keep .js-search-link: Classic's listing script loads the page without a reload.
 *}
{$ciocia_top = !empty($ciocia_position) && $ciocia_position == 'top'}
<nav class="ciocia-pagination{if $ciocia_top} ciocia-pagination--top{/if}" aria-label="{if $ciocia_top}Strony produktów (nad listą){else}Strony produktów{/if}">
  {if !$ciocia_top}
    {block name='pagination_summary'}
      <p class="ciocia-pagination__summary">
        {l s='Showing %from%-%to% of %total% item(s)' d='Shop.Theme.Catalog' sprintf=['%from%' => $pagination.items_shown_from ,'%to%' => $pagination.items_shown_to, '%total%' => $pagination.total_items]}
      </p>
    {/block}
  {/if}

  {block name='pagination_page_list'}
    {if $pagination.should_be_displayed}
      <ul class="ciocia-pagination__list">
        {foreach from=$pagination.pages item="page"}
          <li class="ciocia-pagination__item">
            {if $page.type === 'spacer'}
              <span class="ciocia-pagination__link ciocia-pagination__link--spacer" aria-hidden="true">&hellip;</span>
            {elseif $page.type === 'previous' || $page.type === 'next'}
              {if $page.clickable}
                <a rel="{$page.type|replace:'previous':'prev'}" href="{$page.url}" class="ciocia-pagination__link ciocia-pagination__link--{$page.type} js-search-link">
              {else}
                <span class="ciocia-pagination__link ciocia-pagination__link--{$page.type} is-disabled">
              {/if}
                {if $page.type === 'previous'}
                  <i class="material-icons" aria-hidden="true">chevron_left</i>
                  <span class="ciocia-pagination__word">{l s='Previous' d='Shop.Theme.Actions'}</span>
                {else}
                  <span class="ciocia-pagination__word">{l s='Next' d='Shop.Theme.Actions'}</span>
                  <i class="material-icons" aria-hidden="true">chevron_right</i>
                {/if}
              {if $page.clickable}</a>{else}</span>{/if}
            {elseif $page.current}
              <span class="ciocia-pagination__link is-current" aria-current="page">{$page.page}</span>
            {else}
              <a rel="nofollow" href="{$page.url}" class="ciocia-pagination__link js-search-link">{$page.page}</a>
            {/if}
          </li>
        {/foreach}
      </ul>
    {/if}
  {/block}
</nav>
