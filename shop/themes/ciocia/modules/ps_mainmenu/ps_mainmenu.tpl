{**
 * 2007-2020 PrestaShop SA and Contributors
 *
 * NOTICE OF LICENSE
 *
 * This source file is subject to the Academic Free License 3.0 (AFL-3.0)
 * that is bundled with this package in the file LICENSE.txt.
 * It is also available through the world-wide-web at this URL:
 * https://opensource.org/licenses/AFL-3.0
 * If you did not receive a copy of the license and are unable to
 * obtain it through the world-wide-web, please send an email
 * to license@prestashop.com so we can send you a copy immediately.
 *
 * DISCLAIMER
 *
 * Do not edit or add to this file if you wish to upgrade PrestaShop to newer
 * versions in the future. If you wish to customize PrestaShop for your
 * needs please refer to https://www.prestashop.com for more information.
 *
 * @author    PrestaShop SA <contact@prestashop.com>
 * @copyright 2007-2020 PrestaShop SA and Contributors
 * @license   https://opensource.org/licenses/AFL-3.0 Academic Free License 3.0 (AFL-3.0)
 * International Registered Trademark & Property of PrestaShop SA
 *}
{assign var=_counter value=0}
{* The "Himalaya" entry of the top menu is also offered as a button in the "Kosmetyki" and "Zdrowie" panels, as on the source. *}
{assign var=_himalaya_url value=''}
{foreach from=$menu.children item=_top_node}
  {if $_top_node.label|lower === 'himalaya'}{assign var=_himalaya_url value=$_top_node.url}{/if}
{/foreach}
{function name="menu" nodes=[] depth=0 parent=null himalaya=''}
    {if $nodes|count}
      <ul class="top-menu"{if $depth == 0} id="top-menu"{/if} data-depth="{$depth}">
        {foreach from=$nodes item=node}
            <li class="{$node.type}{if $node.current} current {/if}{if $node.children|count} ciocia-has-submenu{/if}" id="{$node.page_identifier}">
            {assign var=_counter value=$_counter+1}
              <a
                class="{if $depth >= 0}dropdown-item{/if}{if $depth === 1} dropdown-submenu{/if}"
                href="{$node.url}" data-depth="{$depth}"
                {if $node.open_in_new_window} target="_blank" {/if}
              >
                {if $depth === 0 && $node.label|lower === 'na prezent'}<i class="material-icons ciocia-menu-icon" aria-hidden="true">card_giftcard</i>{/if}
                {if $depth === 0 && $node.label|lower === 'promocje'}<i class="material-icons ciocia-menu-icon" aria-hidden="true">local_offer</i>{/if}
                {if $node.image_urls|count}
                  {foreach from=$node.image_urls item=image_url}
                    <img src="{$image_url}" alt="{$node.label|escape:'htmlall':'UTF-8'}">
                  {/foreach}
                {/if}
                {* The source menu shows this category as "Yogi Tea" (its category page is "Herbaty Yogi Tea"). *}
                {if $node.label === 'Herbaty Yogi Tea'}Yogi Tea{else}{$node.label}{/if}
              </a>
              {if $depth === 1 && !($node.children|count)}
                {* Entry of the left list without children: the desktop panel shows a link to the category on the right (hidden in the drawer, custom.css). *}
                <div class="ciocia-mega__goto">
                  <p>Przejdź do kategorii</p>
                  <a class="ciocia-mega__button" href="{$node.url}">{$node.label}<i class="material-icons" aria-hidden="true">arrow_forward</i></a>
                </div>
              {/if}
              {if $node.children|count}
              {assign var=_expand_id value=10|mt_rand:100000}
              <button type="button" class="ciocia-submenu-toggle" aria-expanded="false" aria-controls="top_sub_menu_{$_expand_id}" aria-label="Podkategorie: {$node.label|escape:'htmlall':'UTF-8'}">
                <i class="material-icons" aria-hidden="true">expand_more</i>
              </button>
              <div {if $depth === 0}class="popover sub-menu js-sub-menu ciocia-submenu"{else}class="ciocia-submenu"{/if} id="top_sub_menu_{$_expand_id}" hidden>
                {if $depth === 0}
                  {* Desktop panel as on the source: header with title and buttons, subcategories on the left, their children on the right. The drawer on phones hides the header (custom.css). *}
                  <div class="ciocia-mega">
                    <div class="ciocia-mega__head">
                      <div class="ciocia-mega__heading">
                        <p class="ciocia-mega__eyebrow">Magiczne Indie</p>
                        <p class="ciocia-mega__title">{$node.label}</p>
                      </div>
                      <div class="ciocia-mega__actions">
                        <a class="ciocia-mega__button" href="{$node.url}">Zobacz całą kategorię<i class="material-icons" aria-hidden="true">arrow_forward</i></a>
                        {if $himalaya && ($node.label|lower === 'kosmetyki' || $node.label|lower === 'zdrowie')}
                          <a class="ciocia-mega__button" href="{$himalaya}">Himalaya<i class="material-icons" aria-hidden="true">arrow_forward</i></a>
                        {/if}
                        <button type="button" class="ciocia-mega__close" aria-label="Zamknij menu"><i class="material-icons" aria-hidden="true">close</i></button>
                      </div>
                    </div>
                    {assign var=_children value=$node.children}
                    {* Order of the left list as on the source (the shop lists the subcategories in import order); entries not named here follow in their own order. *}
                    {assign var=_order value=[]}
                    {if $node.label|lower === 'kosmetyki'}
                      {assign var=_order value=['do ciała', 'do twarzy', 'do włosów', 'higiena i akcesoria', 'kosmetyki bio', 'pielęgnacja okolic oczu', 'dla mężczyzn']}
                    {elseif $node.label|lower === 'zdrowie'}
                      {assign var=_order value=['akcesoria', 'eliksiry ziołowe', 'maści', 'suplementy', 'zioła ajurwedyjskie']}
                    {elseif $node.label|lower === 'różności'}
                      {assign var=_order value=['akcesoria do herbaty', 'akcesoria do jogi i medytacji', 'biżuteria i kamienie szlachetne', 'dla zwierząt', 'figurki i ozdoby', 'fontanny wodne', 'miedziane naczynia do wody', 'misy tybetańskie, gongi, dzwonki i cymbałki', 'odpromienniki i wahadełka', 'środki czystości']}
                    {elseif $node.label|lower === 'żywność'}
                      {assign var=_order value=['herbaty indyjskie', 'napoje', 'oleje i ghee', 'przyprawy', 'superfoods']}
                    {/if}
                    {if $_order|count}
                      {assign var=_children value=[]}
                      {foreach from=$_order item=_wanted}
                        {foreach from=$node.children item=_child}
                          {if $_child.label|lower === $_wanted}{$_children[]=$_child}{/if}
                        {/foreach}
                      {/foreach}
                      {foreach from=$node.children item=_child}
                        {if !($_child.label|lower|in_array:$_order)}{$_children[]=$_child}{/if}
                      {/foreach}
                    {/if}
                    <div class="ciocia-mega__body">
                      {menu nodes=$_children depth=$node.depth parent=$node himalaya=$himalaya}
                    </div>
                  </div>
                {else}
                  <p class="ciocia-mega__subtitle">{$node.label}</p>
                  {menu nodes=$node.children depth=$node.depth parent=$node himalaya=$himalaya}
                {/if}
              </div>
              {/if}
            </li>
        {/foreach}
      </ul>
    {/if}
{/function}

<div class="menu js-top-menu position-static hidden-sm-down" id="_desktop_top_menu">
    {menu nodes=$menu.children himalaya=$_himalaya_url}
    <div class="clearfix"></div>
</div>
