{**
 * Adapted from Classic, copyright since 2007 PrestaShop SA and Contributors.
 * Licensed under the Academic Free License 3.0 (AFL-3.0).
 * https://opensource.org/licenses/AFL-3.0
 *}
{foreach $linkBlocks as $linkBlock}
  <nav class="ciocia-footer-block" aria-labelledby="ciocia-footer-title-{$linkBlock.id}">
    <p class="ciocia-footer-title" id="ciocia-footer-title-{$linkBlock.id}">
      {$linkBlock.title}
      <button class="ciocia-footer-toggle collapsed" type="button" data-toggle="collapse"
              data-target="#ciocia-footer-list-{$linkBlock.id}" aria-controls="ciocia-footer-list-{$linkBlock.id}"
              aria-expanded="false" aria-labelledby="ciocia-footer-title-{$linkBlock.id}">
        <i class="material-icons" aria-hidden="true">expand_more</i>
      </button>
    </p>
    <ul id="ciocia-footer-list-{$linkBlock.id}" class="ciocia-footer-list collapse">
      {foreach $linkBlock.links as $link}
        <li>
          <a id="{$link.id}-{$linkBlock.id}" class="{$link.class}" href="{$link.url}"
             title="{$link.description}" {if !empty($link.target)}target="{$link.target}"{/if}>{$link.title}</a>
        </li>
      {/foreach}
    </ul>
  </nav>
{/foreach}
