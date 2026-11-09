{**
 * Adapted from Classic, copyright since 2007 PrestaShop SA and Contributors.
 * Licensed under the Academic Free License 3.0 (AFL-3.0).
 * https://opensource.org/licenses/AFL-3.0
 *}
{* The source shop has no social block; render it only once links are configured. *}
{block name='block_social'}
  {if $social_links}
    <div class="block-social ciocia-social">
      <ul>
        {foreach from=$social_links item='social_link'}
          <li class="{$social_link.class}"><a href="{$social_link.url}" target="_blank" rel="noopener noreferrer">{$social_link.label}</a></li>
        {/foreach}
      </ul>
    </div>
  {/if}
{/block}
